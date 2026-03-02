from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window


def chunked_stats(path: Path, chunk=1024):
    with rasterio.open(path) as src:
        nodata = src.nodata
        if nodata is None:
            nodata = -9999.0  # fallback

        h, w = src.height, src.width

        n = 0
        s = 0.0
        mn = np.inf
        mx = -np.inf

        for row_off in range(0, h, chunk):
            for col_off in range(0, w, chunk):
                hh = min(chunk, h - row_off)
                ww = min(chunk, w - col_off)
                win = Window(col_off, row_off, ww, hh)

                arr = src.read(1, window=win, masked=True).astype("float64")
                vals = arr.compressed()
                if vals.size == 0:
                    continue

                n += vals.size
                s += float(vals.sum())
                mn = min(mn, float(vals.min()))
                mx = max(mx, float(vals.max()))

        mean = s / n if n else np.nan
        return {"count": n, "min": mn, "max": mx, "mean": mean, "nodata": nodata, "crs": src.crs, "res": src.res}


def compare_dods(path_py: Path, path_qgis: Path, chunk=1024, tol=1e-5):
    with rasterio.open(path_py) as a, rasterio.open(path_qgis) as b:
        # Grid checks (must match for pixel-wise diff)
        if a.crs != b.crs:
            raise ValueError(f"CRS mismatch:\nPython: {a.crs}\nQGIS: {b.crs}")
        if not a.transform.almost_equals(b.transform):
            raise ValueError("Transform mismatch (origin/pixel size differs).")
        if a.width != b.width or a.height != b.height:
            raise ValueError(f"Shape mismatch: Python {a.width}x{a.height}, QGIS {b.width}x{b.height}")

        h, w = a.height, a.width

        max_abs = 0.0
        sum_sq = 0.0
        n = 0
        n_diff = 0

        for row_off in range(0, h, chunk):
            for col_off in range(0, w, chunk):
                hh = min(chunk, h - row_off)
                ww = min(chunk, w - col_off)
                win = Window(col_off, row_off, ww, hh)

                A = a.read(1, window=win, masked=True).astype("float64")
                B = b.read(1, window=win, masked=True).astype("float64")
                mask = np.ma.getmaskarray(A) | np.ma.getmaskarray(B)

                if np.all(mask):
                    continue

                diff = (A.data - B.data)
                d = diff[~mask]

                absd = np.abs(d)
                max_abs = max(max_abs, float(absd.max()))
                sum_sq += float((d * d).sum())
                n += d.size
                n_diff += int((absd > tol).sum())

        rmse = np.sqrt(sum_sq / n) if n else np.nan
        pct_diff = 100.0 * n_diff / n if n else np.nan
        return {"max_abs_diff": max_abs, "rmse": rmse, "n_compared": n, "n_diff_gt_tol": n_diff, "pct_diff_gt_tol": pct_diff}


def find_project_root():
    this_file = Path(__file__).resolve()
    for c in [this_file.parent.parent, this_file.parent]:
        if (c / "Inputs").exists() and (c / "outputs").exists():
            return c
    # fallback
    return this_file.parent.parent


def main():
    project_root = find_project_root()

    py_dod = project_root / "outputs" / "rasters" / "DoD_B_minus_A.tif"
    qgis_dod = project_root / "Inputs" / "newone99.tif"

    print("Python DoD:", py_dod, "exists:", py_dod.exists())
    print("QGIS DoD  :", qgis_dod, "exists:", qgis_dod.exists())
    if not py_dod.exists() or not qgis_dod.exists():
        raise FileNotFoundError("One of the DoD files is missing. Check paths.")

    print("\n--- Stats (valid pixels only) ---")
    print("Python:", chunked_stats(py_dod))
    print("QGIS  :", chunked_stats(qgis_dod))

    print("\n--- Pixel-wise comparison ---")
    comp = compare_dods(py_dod, qgis_dod, tol=1e-5)
    print(comp)

    print("\nInterpretation:")
    print("- If max_abs_diff is ~0 (or <= 1e-5) and pct_diff_gt_tol ~0%, they match.")
    print("- If max_abs_diff is big (e.g., > 0.01 m), they are not the same DoD.")


if __name__ == "__main__":
    main()
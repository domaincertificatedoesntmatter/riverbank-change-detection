from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import matplotlib.pyplot as plt


def ensure_dirs(*dirs: Path):
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def assert_same_grid(src_a, src_b):
    """
    Why this matters:
    - DoD (B - A) is only meaningful if every pixel in A matches the same ground location in B.
    Checks:
    - CRS: same coordinate reference system
    - transform: same pixel origin + pixel size
    - shape: same width/height
    """
    if src_a.crs != src_b.crs:
        raise ValueError(f"CRS mismatch:\nA: {src_a.crs}\nB: {src_b.crs}")

    # transform is an affine transform (origin + pixel size + rotation)
    # almost_equals avoids tiny floating rounding issues.
    if not src_a.transform.almost_equals(src_b.transform):
        raise ValueError(f"Transform mismatch:\nA: {src_a.transform}\nB: {src_b.transform}")

    if (src_a.width != src_b.width) or (src_a.height != src_b.height):
        raise ValueError(f"Shape mismatch:\nA: {src_a.width}x{src_a.height}\n"
                         f"B: {src_b.width}x{src_b.height}")

    if src_a.res != src_b.res:
        raise ValueError(f"Pixel size mismatch:\nA: {src_a.res}\nB: {src_b.res}")


def main():
    # ----------------------------
    # USER SETTINGS (edit if needed)
    # ----------------------------
    project_root = project_root = Path(__file__).resolve().parent

    A_path = project_root / "Inputs" / "A_corridor_1m_p.tif"
    B_path = project_root / "Inputs" / "B_corridor_1m_aligned_final.tif"

    threshold_m = 0.10  # meters (your example)

    out_rasters = project_root / "outputs" / "rasters"
    out_tables  = project_root / "outputs" / "tables"
    out_figs    = project_root / "outputs" / "figures"
    ensure_dirs(out_rasters, out_tables, out_figs)

    dod_path   = out_rasters / "DoD_B_minus_A.tif"
    cls_path   = out_rasters / "class_-1_0_1.tif"
    ero_path   = out_rasters / "erosion_dod.tif"
    dep_path   = out_rasters / "deposition_dod.tif"

    stats_csv  = out_tables / "dod_erosion_deposition_stats.csv"
    hist_png   = out_figs / "dod_histogram.png"
    map_png    = out_figs / "dod_map.png"
    cls_png    = out_figs / "class_map.png"

    # ----------------------------
    # OPEN INPUTS + VERIFY ALIGNMENT
    # ----------------------------
    with rasterio.open(A_path) as srcA, rasterio.open(B_path) as srcB:
        assert_same_grid(srcA, srcB)

        nodataA = srcA.nodata
        nodataB = srcB.nodata
        if nodataA is None or nodataB is None:
            print("WARNING: One input has nodata=None in metadata. "
                  "Masked reads may be unreliable. Consider setting nodata in QGIS or with gdal_translate.")
        print(f"A nodata: {nodataA}, B nodata: {nodataB}")

        # Pixel area (m²) from resolution (EPSG:2154 is meters horizontally)
        pixel_w, pixel_h = srcA.res
        pixel_area = abs(pixel_w * pixel_h)

        # Output profiles (how we write GeoTIFFs)
        base_profile = srcA.profile.copy()

        # IMPORTANT: remove inherited block/tile settings from the source
        for k in ["tiled", "blockxsize", "blockysize"]:
            base_profile.pop(k, None)

        # Standard GeoTIFF tiling: multiples of 16 (256 is common and fast)
        BLOCK = 256

        float_profile = base_profile.copy()
        float_profile.update(
            dtype="float32",
            count=1,
            nodata=-9999.0,
            compress="lzw",
            tiled=True,
            blockxsize=BLOCK,
            blockysize=BLOCK,
            bigtiff="if_safer"
        )

        cls_profile = base_profile.copy()
        cls_profile.update(
            dtype="int16",
            count=1,
            nodata=-9999,
            compress="lzw",
            tiled=True,
            blockxsize=BLOCK,
            blockysize=BLOCK,
            bigtiff="if_safer"
        )
        # Create output datasets
        with rasterio.open(dod_path, "w", **float_profile) as dst_dod, \
             rasterio.open(ero_path, "w", **float_profile) as dst_ero, \
             rasterio.open(dep_path, "w", **float_profile) as dst_dep, \
             rasterio.open(cls_path, "w", **cls_profile) as dst_cls:

            # ----------------------------
            # CHUNKED PROCESSING
            # ----------------------------
            height, width = srcA.height, srcA.width
            chunk = 1024  # pixels (adjust if you want smaller/larger)

            # Running totals for stats
            n_valid = 0
            dod_sum = 0.0
            dod_min = np.inf
            dod_max = -np.inf

            n_ero = 0
            n_dep = 0
            vol_ero = 0.0  # will be negative (since DoD is negative)
            vol_dep = 0.0  # positive

            # For histogram (fixed range; covers your known min/max comfortably)
            bins = np.linspace(-5, 10, 301)
            hist_counts = np.zeros(len(bins) - 1, dtype=np.int64)

            for row_off in range(0, height, chunk):
                for col_off in range(0, width, chunk):
                    h = min(chunk, height - row_off)
                    w = min(chunk, width - col_off)
                    window = Window(col_off, row_off, w, h)

                    # masked=True uses nodata / masks so invalid pixels become masked :contentReference[oaicite:1]{index=1}
                    A = srcA.read(1, window=window, masked=True).astype("float32")
                    B = srcB.read(1, window=window, masked=True).astype("float32")

                    # Combine masks: if either A or B is nodata, result is nodata
                    mask = np.ma.getmaskarray(A) | np.ma.getmaskarray(B)

                    # Compute DoD (B - A) only where valid
                    dod = np.empty((h, w), dtype="float32")
                    dod[:] = float_profile["nodata"]
                    dod_valid = (B.data - A.data)
                    dod[~mask] = dod_valid[~mask]

                    # Write DoD
                    dst_dod.write(dod, 1, window=window)

                    # Classification: -1 erosion, 0 stable, +1 deposition, nodata elsewhere
                    cls = np.empty((h, w), dtype="int16")
                    cls[:] = cls_profile["nodata"]
                    cls[~mask] = 0

                    erosion_mask = (~mask) & (dod <= -threshold_m)
                    deposition_mask = (~mask) & (dod >= threshold_m)

                    cls[erosion_mask] = -1
                    cls[deposition_mask] = 1
                    dst_cls.write(cls, 1, window=window)

                    # Thresholded erosion/deposition rasters (keep DoD values, nodata elsewhere)
                    ero = np.empty((h, w), dtype="float32")
                    dep = np.empty((h, w), dtype="float32")
                    ero[:] = float_profile["nodata"]
                    dep[:] = float_profile["nodata"]
                    ero[erosion_mask] = dod[erosion_mask]
                    dep[deposition_mask] = dod[deposition_mask]
                    dst_ero.write(ero, 1, window=window)
                    dst_dep.write(dep, 1, window=window)

                    # ----------------------------
                    # STATS UPDATE (only valid pixels)
                    # ----------------------------
                    valid_vals = dod[~mask]
                    if valid_vals.size > 0:
                        n_valid += valid_vals.size
                        dod_sum += float(valid_vals.sum())
                        dod_min = min(dod_min, float(valid_vals.min()))
                        dod_max = max(dod_max, float(valid_vals.max()))

                        # histogram update
                        c, _ = np.histogram(valid_vals, bins=bins)
                        hist_counts += c

                    # erosion/deposition counts + volumes
                    n_ero_chunk = int(erosion_mask.sum())
                    n_dep_chunk = int(deposition_mask.sum())
                    n_ero += n_ero_chunk
                    n_dep += n_dep_chunk

                    if n_ero_chunk > 0:
                        vol_ero += float(dod[erosion_mask].sum()) * pixel_area  # negative
                    if n_dep_chunk > 0:
                        vol_dep += float(dod[deposition_mask].sum()) * pixel_area  # positive

            # Final DoD mean
            dod_mean = dod_sum / n_valid if n_valid > 0 else np.nan

    # ----------------------------
    # SAVE STATS TABLE
    # ----------------------------
    area_ero = n_ero * pixel_area
    area_dep = n_dep * pixel_area

    # volumes: erosion volume magnitude is abs(vol_ero)
    results = {
        "threshold_m": [threshold_m],
        "pixel_area_m2": [pixel_area],
        "valid_pixel_count": [n_valid],
        "dod_min_m": [dod_min],
        "dod_max_m": [dod_max],
        "dod_mean_m": [dod_mean],
        "erosion_area_m2": [area_ero],
        "deposition_area_m2": [area_dep],
        "erosion_volume_m3_signed": [vol_ero],
        "deposition_volume_m3": [vol_dep],
        "erosion_volume_m3_magnitude": [abs(vol_ero)],
        "net_volume_m3_dep_minus_ero": [vol_dep + vol_ero],  # vol_ero is negative
    }
    df = pd.DataFrame(results)
    df.to_csv(stats_csv, index=False)
    print(f"Saved stats: {stats_csv}")

    # ----------------------------
    # QA/QC PLOTS
    # ----------------------------
    # 1) Histogram (from accumulated counts)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    plt.figure()
    plt.plot(bin_centers, hist_counts)
    plt.xlabel("DoD (m)  [B - A]")
    plt.ylabel("Pixel count")
    plt.title("DoD histogram (valid pixels only)")
    plt.grid(True, alpha=0.3)
    plt.savefig(hist_png, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved histogram: {hist_png}")

    # 2) Quick maps (downsample read to avoid huge RAM use)
    with rasterio.open(dod_path) as src:
        # Downsample factor for plotting
        scale = 10  # bigger = smaller image; 10 is a good start
        out_h = max(1, src.height // scale)
        out_w = max(1, src.width // scale)

        dod_small = src.read(
            1,
            out_shape=(out_h, out_w),
            resampling=rasterio.enums.Resampling.nearest
        ).astype("float32")

        # Mask nodata
        nodata = src.nodata
        dod_small = np.ma.masked_equal(dod_small, nodata)

        # Extent for correct axes (meters)
        b = src.bounds
        extent = [b.left, b.right, b.bottom, b.top]

    plt.figure()
    plt.imshow(dod_small, extent=extent)
    plt.colorbar(label="DoD (m) [B - A]")
    plt.title("DoD map (downsampled for QA/QC)")
    plt.xlabel("Easting (m)")
    plt.ylabel("Northing (m)")
    plt.savefig(map_png, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved DoD map: {map_png}")

    with rasterio.open(cls_path) as src:
        scale = 10
        out_h = max(1, src.height // scale)
        out_w = max(1, src.width // scale)

        cls_small = src.read(
            1,
            out_shape=(out_h, out_w),
            resampling=rasterio.enums.Resampling.nearest
        ).astype("int16")

        nodata = src.nodata
        cls_small = np.ma.masked_equal(cls_small, nodata)

        b = src.bounds
        extent = [b.left, b.right, b.bottom, b.top]

    plt.figure()
    plt.imshow(cls_small, extent=extent)
    plt.colorbar(label="Class (-1 erosion, 0 stable, +1 deposition)")
    plt.title(f"Erosion/Deposition classification (thr={threshold_m} m)")
    plt.xlabel("Easting (m)")
    plt.ylabel("Northing (m)")
    plt.savefig(cls_png, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved class map: {cls_png}")

    print("\nDONE.")
    print(f"Outputs written to: {Path('outputs').resolve()}")


if __name__ == "__main__":
    main()
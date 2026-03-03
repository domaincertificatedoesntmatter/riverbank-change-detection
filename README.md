# River Corridor Elevation Change (DoD) — Villerest Project

## 1. Objective
Quantify river corridor elevation change between two LiDAR-derived DEM rasters using a DEM of Difference (DoD) approach, then map thresholded erosion/deposition and compute area and volume statistics.

## 2. Data
- Coordinate system: **EPSG:2154** (meters)
- Inputs (GeoTIFF, 1 m grid, aligned):
  - Older DEM (A): `Inputs/A_corridor_1m_p.tif`
  - Recent DEM (B): `Inputs/B_corridor_1m_aligned_final.tif`
- NoData: **-9999**
- Pixel size: **1 m × 1 m** (pixel area = 1 m²)

## 3. Preprocessing (QGIS summary)
1. Digitized river centerline.
2. Built a corridor buffer around the centerline.
3. Clipped both DEMs to the corridor.
4. Resampled/aligned DEM B to match DEM A on a **1 m grid** (same CRS, extent, transform).
5. Standardized NoData to **-9999**.

## 4. Method
### 4.1 DEM of Difference
DoD is computed per pixel as:

**DoD = B − A**

Positive DoD = deposition (surface gained elevation)  
Negative DoD = erosion (surface lost elevation)

### 4.2 Thresholding (minimum detection threshold)
A uniform threshold **T = 0.10 m** is applied:

- Erosion if **DoD ≤ −T**
- Deposition if **DoD ≥ +T**
- Stable otherwise

A classification raster is produced with values:
- **-1 = erosion**
- **0 = stable**
- **+1 = deposition**

### 4.3 Area and Volume
Pixel area: **A_pix = 1 m²**

- Area = (number of classified pixels) × A_pix  
- Volume = Σ(DoD × A_pix) over classified pixels

Erosion volume is reported as:
- signed (negative), and
- magnitude (absolute value)

## 5. Results (threshold = 0.10 m)
Statistics from: `outputs/tables/dod_erosion_deposition_stats.csv`

- Valid corridor area (from valid pixels): **1,895,198 m²**
- DoD min: **-7.028 m**
- DoD max: **+9.002 m**
- DoD mean: **+0.172 m**

### 5.1 Erosion / Deposition areas
- Erosion area: **105,311 m²**
- Deposition area: **1,191,342 m²**

### 5.2 Volumes
- Erosion volume (signed): **-46,587.65 m³**
- Erosion volume (magnitude): **46,587.65 m³**
- Deposition volume: **347,429.08 m³**
- Net volume (Dep − Ero): **+300,841.43 m³**

## 6. QA/QC Figures
**DoD histogram**
![](../outputs/figures/dod_histogram.png)

**DoD map (QA/QC)**
![](../outputs/figures/dod_map.png)

**Erosion/Deposition classification**
![](../outputs/figures/class_map.png)

## 7. Notes / Limitations
- Thresholding uses a uniform minimum detection threshold; a more advanced approach would incorporate spatially varying uncertainty.
- Results are limited to the corridor mask and depend on DEM preprocessing quality and vertical errors.

## 8. References
- Rasterio documentation (reading/writing rasters, masks, windows): https://rasterio.readthedocs.io/

# Riverbank / River Corridor Change Detection (DoD)

This repo computes DEM of Difference (DoD) between two LiDAR-derived DEM rasters (EPSG:2154), then produces:
- DoD raster (B − A)
- thresholded erosion/deposition rasters (T = 0.10 m)
- classification raster (-1, 0, +1)
- area and volume statistics (CSV)
- QA/QC figures (histogram + maps)

## How to run
1. Put input rasters in `Inputs/` (not committed to GitHub):
   - `A_corridor_1m_p.tif`
   - `B_corridor_1m_aligned_final.tif`

2. Create environment and install:
   ```bash
   pip install rasterio numpy pandas matplotlib



# Riverbank / River Corridor Change Detection (DoD) — Villerest Project

This repository replicates a DEM of Difference (DoD) workflow to quantify river corridor elevation change between two LiDAR-derived DEM rasters. It produces thresholded erosion/deposition maps, area and volume statistics, and QA/QC plots.

---

## Repository Contents

- **`tools/dod_workflow.py`** — main workflow (reads A/B, computes DoD, threshold maps, stats, plots)
- **`tools/verify_qgis_dod.py`** — optional verification against a QGIS-produced DoD
- **`outputs/tables/`** — CSV statistics output
- **`outputs/figures/`** — QA/QC figures (PNG)
- **`report/report.md`** — short report (same content as below)

> Large GeoTIFFs are intentionally excluded from GitHub (see `.gitignore`).

---

## How to Run

### 1) Install dependencies
```bash
pip install rasterio numpy pandas matplotlib

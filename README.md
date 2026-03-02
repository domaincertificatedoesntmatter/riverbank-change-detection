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

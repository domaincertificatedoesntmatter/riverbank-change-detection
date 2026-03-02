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

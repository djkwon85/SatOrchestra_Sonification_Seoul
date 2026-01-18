# -*- coding: utf-8 -*-
"""
A_S2_Download_Seasonal_FullCover_Tuned.py

Features:
1. Searches for imagery that fully covers Seoul (Cover > 99%) for each season in 2025.
2. [Update] Delayed the Spring period to after mid-April to acquire imagery with high vegetation vitality.
3. Downloads the optimal image with the least cloud cover among them.
"""

import os
import geopandas as gpd
from datetime import datetime, timedelta
from pystac_client import Client
import planetary_computer
import rioxarray
from shapely.geometry import mapping, shape 

# ──────────────────────────────────────────────────────────
# 1. Configuration
# ──────────────────────────────────────────────────────────
BASE_DIR = os.getcwd()
BOUNDARY_PATH = os.path.join(BASE_DIR, "Seoul.geojson")
OUTPUT_DIR = os.path.join(BASE_DIR, "raw_data", "Sentinel-2")

REQUIRED_ASSETS = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]

# ★ [Update] Spring period change: Exclude March (Brown), focus on mid-April to end of May (Green)
SEASONS = {
    "Spring": [("2025-04-15", "2025-05-31")], 
    "Summer": [("2025-06-15", "2025-08-15")],
    "Autumn": [("2025-09-15", "2025-11-15")],
    "Winter": [("2025-01-01", "2025-02-15"), ("2025-12-15", "2025-12-31")]
}

SEARCH_CLOUD_LIMIT = 50 
MIN_COVERAGE_PCT = 99.0

# ──────────────────────────────────────────────────────────
# 2. Utility Functions
# ──────────────────────────────────────────────────────────
def get_aoi_gdf(geojson_path):
    if not os.path.exists(geojson_path):
        raise FileNotFoundError(f"❌ Boundary file not found: {geojson_path}")
    return gpd.read_file(geojson_path)

def download_cropped_asset(url, save_path, aoi_gdf):
    if os.path.exists(save_path):
        print(f"    [Skip] Already exists: {os.path.basename(save_path)}")
        return
    try:
        with rioxarray.open_rasterio(url) as src:
            aoi_projected = aoi_gdf.to_crs(src.rio.crs)
            clipped = src.rio.clip(aoi_projected.geometry, from_disk=True)
            clipped.rio.to_raster(save_path, compress='LZW', tiled=True, dtype='float32')
        print(f"    [Done] Download complete: {os.path.basename(save_path)}")
    except Exception as e:
        print(f"    [Fail] Download failed: {e}")
        if os.path.exists(save_path): os.remove(save_path)

def search_best_full_cover_item(catalog, geom, aoi_shape, date_ranges, cloud_limit, extend_days=0):
    """
    Finds the optimal image considering both cloud cover and coverage (area).
    """
    raw_candidates = []
    
    # 1. Date range extension and STAC search
    search_ranges = []
    if extend_days > 0:
        print(f"  ↪ No suitable image within period. Extending search by ±{extend_days} days...")
        
    for start, end in date_ranges:
        s_date = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=extend_days)
        e_date = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=extend_days)
        search_ranges.append(f"{s_date.strftime('%Y-%m-%d')}/{e_date.strftime('%Y-%m-%d')}")

    for dr in search_ranges:
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            intersects=geom,
            datetime=dr,
            query={"eo:cloud_cover": {"lt": cloud_limit}}
        )
        raw_candidates.extend(list(search.item_collection()))

    if not raw_candidates:
        return None

    # 2. Coverage filtering
    valid_candidates = []
    aoi_area = aoi_shape.area 
    
    print(f"  🔍 Checking 'Full Seoul Coverage' for {len(raw_candidates)} candidates...")
    
    for item in raw_candidates:
        item_geom = shape(item.geometry)
        intersection_area = aoi_shape.intersection(item_geom).area
        coverage_pct = (intersection_area / aoi_area) * 100.0
        
        if coverage_pct >= MIN_COVERAGE_PCT:
            valid_candidates.append(item)
    
    print(f"  ✓ Candidates satisfying condition (Cover>{MIN_COVERAGE_PCT}%): {len(valid_candidates)}")

    if not valid_candidates:
        return None

    # 3. Sort by least cloud cover
    valid_candidates.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
    return valid_candidates[0]

# ──────────────────────────────────────────────────────────
# 3. Main Logic
# ──────────────────────────────────────────────────────────
def main():
    print(f"--- Sentinel-2 Full Coverage Download (Seoul: Tuned Season) ---")
    
    try:
        aoi_gdf = get_aoi_gdf(BOUNDARY_PATH)
        aoi_gdf_4326 = aoi_gdf.to_crs(epsg=4326)
        search_geom = mapping(aoi_gdf_4326.geometry.iloc[0])
        aoi_shape = shape(search_geom)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for season, ranges in SEASONS.items():
        print(f"\n🌸 [{season}] Searching for optimal image...")
        
        best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=0)
        
        if best_item is None:
            best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=14)
            
        if best_item is None:
            best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=30)

        if best_item is None:
            print(f"  ⚠️ Failed: No clear image covering the entire Seoul area within the period.")
            continue

        d_str = best_item.datetime.strftime("%Y-%m-%d")
        cc = best_item.properties['eo:cloud_cover']
        print(f"  ✅ Final Selection: {d_str} (Cloud: {cc:.2f}%) - Full Seoul Coverage")
        
        scene_dir = os.path.join(OUTPUT_DIR, best_item.id)
        os.makedirs(scene_dir, exist_ok=True)
        
        assets = best_item.assets
        for key in REQUIRED_ASSETS:
            if key in assets:
                url = assets[key].href
                fname = url.split("?")[0].split("/")[-1]
                save_path = os.path.join(scene_dir, fname)
                download_cropped_asset(url, save_path, aoi_gdf)
            else:
                print(f"    [Warn] {key} band missing")

    print("\n🎉 All downloads complete.")

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
A_2_S2_Download_Seasonal_FullCover_Tuned.py

기능:
1. 2025년 계절별로 서울 전체(Boundary)를 온전히 덮는(Cover > 99%) 영상을 찾습니다.
2. [Update] 봄 기간을 4월 중순 이후로 늦춰 식생 활력도가 높은 영상을 확보합니다.
3. 그중 구름이 가장 적은 최적의 영상을 다운로드합니다.
"""

import os
import geopandas as gpd
from datetime import datetime, timedelta
from pystac_client import Client
import planetary_computer
import rioxarray
from shapely.geometry import mapping, shape 

# ──────────────────────────────────────────────────────────
# 1. 설정 (Configuration)
# ──────────────────────────────────────────────────────────
BASE_DIR = os.getcwd()
BOUNDARY_PATH = os.path.join(BASE_DIR, "Seoul.geojson")
OUTPUT_DIR = os.path.join(BASE_DIR, "raw_data", "Sentinel-2")

REQUIRED_ASSETS = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]

# ★ [수정] 봄 기간 변경: 3월(갈색) 제외, 4월 중순~5월 말(녹색) 집중
SEASONS = {
    "Spring": [("2025-04-15", "2025-05-31")], 
    "Summer": [("2025-06-15", "2025-08-15")],
    "Autumn": [("2025-09-15", "2025-11-15")],
    "Winter": [("2025-01-01", "2025-02-15"), ("2025-12-15", "2025-12-31")]
}

SEARCH_CLOUD_LIMIT = 50 
MIN_COVERAGE_PCT = 99.0

# ──────────────────────────────────────────────────────────
# 2. 유틸리티 함수
# ──────────────────────────────────────────────────────────
def get_aoi_gdf(geojson_path):
    if not os.path.exists(geojson_path):
        raise FileNotFoundError(f"❌ 경계 파일을 찾을 수 없습니다: {geojson_path}")
    return gpd.read_file(geojson_path)

def download_cropped_asset(url, save_path, aoi_gdf):
    if os.path.exists(save_path):
        print(f"    [Skip] 이미 존재함: {os.path.basename(save_path)}")
        return
    try:
        with rioxarray.open_rasterio(url) as src:
            aoi_projected = aoi_gdf.to_crs(src.rio.crs)
            clipped = src.rio.clip(aoi_projected.geometry, from_disk=True)
            clipped.rio.to_raster(save_path, compress='LZW', tiled=True, dtype='float32')
        print(f"    [Done] 다운로드 완료: {os.path.basename(save_path)}")
    except Exception as e:
        print(f"    [Fail] 다운로드 실패: {e}")
        if os.path.exists(save_path): os.remove(save_path)

def search_best_full_cover_item(catalog, geom, aoi_shape, date_ranges, cloud_limit, extend_days=0):
    """
    구름량 + 커버리지(면적)를 모두 고려하여 최적의 영상을 찾습니다.
    """
    raw_candidates = []
    
    # 1. 기간 확장 및 STAC 검색
    search_ranges = []
    if extend_days > 0:
        print(f"  ↪ 기간 내 적합한 영상 없음. ±{extend_days}일 확장 검색...")
        
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

    # 2. 커버리지 필터링
    valid_candidates = []
    aoi_area = aoi_shape.area 
    
    print(f"  🔍 후보 {len(raw_candidates)}개 중 '서울 전체 포함' 여부 검사...")
    
    for item in raw_candidates:
        item_geom = shape(item.geometry)
        intersection_area = aoi_shape.intersection(item_geom).area
        coverage_pct = (intersection_area / aoi_area) * 100.0
        
        if coverage_pct >= MIN_COVERAGE_PCT:
            valid_candidates.append(item)
    
    print(f"  ✓ 조건 만족(Cover>{MIN_COVERAGE_PCT}%) 후보: {len(valid_candidates)}개")

    if not valid_candidates:
        return None

    # 3. 구름 적은 순 정렬
    valid_candidates.sort(key=lambda x: x.properties.get("eo:cloud_cover", 100))
    return valid_candidates[0]

# ──────────────────────────────────────────────────────────
# 3. 메인 로직
# ──────────────────────────────────────────────────────────
def main():
    print(f"--- Sentinel-2 Full Coverage Download (Seoul: Tuned Season) ---")
    
    try:
        aoi_gdf = get_aoi_gdf(BOUNDARY_PATH)
        aoi_gdf_4326 = aoi_gdf.to_crs(epsg=4326)
        search_geom = mapping(aoi_gdf_4326.geometry.iloc[0])
        aoi_shape = shape(search_geom)
    except Exception as e:
        print(f"❌ 오류: {e}")
        return

    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for season, ranges in SEASONS.items():
        print(f"\n🌸 [{season}] 최적 영상 검색 중...")
        
        best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=0)
        
        if best_item is None:
            best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=14)
            
        if best_item is None:
            best_item = search_best_full_cover_item(catalog, search_geom, aoi_shape, ranges, SEARCH_CLOUD_LIMIT, extend_days=30)

        if best_item is None:
            print(f"  ⚠️ 실패: 해당 기간 내에 서울 전체를 덮는 맑은 영상이 없습니다.")
            continue

        d_str = best_item.datetime.strftime("%Y-%m-%d")
        cc = best_item.properties['eo:cloud_cover']
        print(f"  ✅ 최종 선정: {d_str} (구름: {cc:.2f}%) - 서울 전체 포함")
        
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
                print(f"    [Warn] {key} 밴드 없음")

    print("\n🎉 모든 다운로드 완료.")

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
V3_1_S2_JSON_Gen_Tuned.py
- [Fix] 봄철 식생 감지율 저하 해결
- [Update] 식생(Vegetation) 임계값 완화 (0.3 -> 0.2)
- [Update] 건물(Buildings) 임계값 강화 (0.0 -> 0.05, 노이즈 제거)
- [Update] 시각화용 '면적 비율(%)' 데이터 정밀 계산
"""

import os
import glob
import json
import re
import numpy as np
import rasterio
from rasterio.enums import Resampling

BASE_DIR = os.getcwd()
RAW_S2_DIR = os.path.join(BASE_DIR, "raw_data", "Sentinel-2")
OUT_SCORE_DIR = os.path.join(BASE_DIR, "processed_data", "Daily_Music_Scores")
os.makedirs(OUT_SCORE_DIR, exist_ok=True)

# Band 03(Green), 04(Red), 08(NIR), 11(SWIR)
TARGET_BANDS = ["B03", "B04", "B08", "B11", "SCL"] 
VALID_SCL_CLASSES = [4, 5, 6, 7] # 4:식생, 5:나지, 6:물, 7:기타

SCAN_STRIDE = 10

# ★ [핵심 수정] 임계값 튜닝
# 봄철 새싹/도심지 녹지 감지를 위해 0.3 -> 0.2로 낮춤
VEG_THRESHOLD = 0.2     
# 건물 오탐지(맨땅 등)를 줄이기 위해 0.0 -> 0.05로 높임
BUILD_THRESHOLD = 0.05  
# 물 감지 (그대로 유지)
WATER_THRESHOLD = 0.0   

def calculate_index(b1, b2):
    denom = b1 + b2
    denom[denom == 0] = 0.0001
    return (b1 - b2) / denom

def get_zscore(val, mean, std):
    if std == 0: return 0
    z = (val - mean) / std
    return float(z)

# 소리용 데이터 증폭 함수 (Robust Norm)
def normalize_robust(data):
    valid = data[~np.isnan(data)]
    if valid.size == 0: return data
    p2, p98 = np.percentile(valid, (2, 98))
    if p98 - p2 == 0: return data
    norm = (data - p2) / (p98 - p2)
    return np.clip(norm, 0, 1)

def process_s2_area_music():
    print(f">>> Sentinel-2 Data Gen (Tuned Thresholds)...")
    print(f"    THRESHOLDS -> Veg: {VEG_THRESHOLD}, Build: {BUILD_THRESHOLD}, Water: {WATER_THRESHOLD}")
    
    s2_folders = sorted([f for f in glob.glob(os.path.join(RAW_S2_DIR, "*")) if os.path.isdir(f)])
    
    for folder in s2_folders:
        tif_files = glob.glob(os.path.join(folder, "*.tif"))
        if not tif_files: continue
        
        sample_file = os.path.basename(tif_files[0])
        m = re.search(r"_(\d{8})T", sample_file)
        if not m: continue
        date_str = m.group(1)
        out_json = os.path.join(OUT_SCORE_DIR, f"{date_str}_Music_Score.json")
        
        print(f"\nProcessing [{date_str}]...")

        def find_band(b_key):
            c = [f for f in tif_files if b_key in f]
            return c[0] if c else None

        band_paths = [find_band(b) for b in TARGET_BANDS]
        if None in band_paths: continue
        
        try:
            with rasterio.open(band_paths[0]) as src_ref:
                H, W = src_ref.shape
                stack = np.zeros((len(TARGET_BANDS), H, W), dtype=np.float32)

            for i, bp in enumerate(band_paths):
                with rasterio.open(bp) as src:
                    if src.shape != (H, W):
                        arr = src.read(1, out_shape=(H, W), resampling=Resampling.nearest)
                    else:
                        arr = src.read(1)
                    stack[i] = arr

            # 마스킹
            scl = stack[-1]
            mask_invalid = (~np.isin(scl, VALID_SCL_CLASSES)) | (stack[0] == 0)
            
            b_grn   = stack[0]
            b_red   = stack[1]
            b_nir   = stack[2]
            b_swir  = stack[3]

            for b_arr in [b_grn, b_red, b_nir, b_swir]:
                b_arr[mask_invalid] = np.nan

            # 1. Raw Indices (면적 계산용)
            ndvi_raw = calculate_index(b_nir, b_red)  # 식생
            ndbi_raw = calculate_index(b_swir, b_nir) # 건물
            ndwi_raw = calculate_index(b_grn, b_nir)  # 물

            # 2. Normalized Indices (소리/음악용)
            ndvi_norm = normalize_robust(ndvi_raw)
            ndbi_norm = normalize_robust(ndbi_raw)
            ndwi_norm = normalize_robust(ndwi_raw)

            # 3. Global Stats for Z-score
            def get_global_stats(m_data):
                valid = m_data[~np.isnan(m_data)]
                if valid.size == 0: return 0, 1
                return np.mean(valid), np.std(valid)

            ndvi_mean, ndvi_std = get_global_stats(ndvi_raw)
            ndbi_mean, ndbi_std = get_global_stats(ndbi_raw)

            daily_score = []

            # 4. 스캔 및 면적 계산
            for t in range(0, W, SCAN_STRIDE):
                # A. 소리용 데이터 (평균 강도)
                def get_col_mean(col):
                    v = col[~np.isnan(col)]
                    return float(np.mean(v)) if v.size > 0 else 0.0

                v_ndvi = get_col_mean(ndvi_norm[:, t])
                v_ndbi = get_col_mean(ndbi_norm[:, t])
                v_ndwi = get_col_mean(ndwi_norm[:, t])

                # Z-Score (음높이용)
                raw_ndvi_mean = get_col_mean(ndvi_raw[:, t])
                raw_ndbi_mean = get_col_mean(ndbi_raw[:, t])
                z_ndvi = get_zscore(raw_ndvi_mean, ndvi_mean, ndvi_std)
                z_ndbi = get_zscore(raw_ndbi_mean, ndbi_mean, ndbi_std)

                # B. ★ 시각화용 데이터 (면적 비율 %) - 튜닝된 임계값 적용
                col_ndvi_raw = ndvi_raw[:, t]
                col_ndbi_raw = ndbi_raw[:, t]
                col_ndwi_raw = ndwi_raw[:, t]
                
                valid_pixels = np.sum(~np.isnan(col_ndvi_raw)) # 유효 픽셀 수
                
                if valid_pixels > 0:
                    # 변경된 Threshold 적용
                    pct_veg   = np.sum(col_ndvi_raw > VEG_THRESHOLD)   / valid_pixels
                    pct_build = np.sum(col_ndbi_raw > BUILD_THRESHOLD) / valid_pixels
                    pct_water = np.sum(col_ndwi_raw > WATER_THRESHOLD) / valid_pixels
                else:
                    pct_veg, pct_build, pct_water = 0.0, 0.0, 0.0

                # 리듬 트리거 (소리용)
                r_kick  = v_ndbi if v_ndbi > 0.05 else 0.0 
                r_snare = v_ndvi if v_ndvi > 0.1 else 0.0
                r_hihat = v_ndwi if v_ndwi > 0.05 else 0.0 

                daily_score.append({
                    "time_step": t,
                    "melody": { 
                        "ndvi": {"vol": v_ndvi, "zscore": z_ndvi}, 
                        "ndbi": {"vol": v_ndbi, "zscore": z_ndbi}, 
                        "ndwi": {"vol": v_ndwi, "zscore": 0.0}
                    },
                    "visuals": { 
                        "pct_veg": float(pct_veg),
                        "pct_build": float(pct_build),
                        "pct_water": float(pct_water)
                    },
                    "rhythm": {
                        "kick": r_kick,
                        "snare": r_snare,
                        "hihat": r_hihat
                    }
                })

            with open(out_json, "w") as f:
                json.dump(daily_score, f)
            print(f"  ✓ JSON Saved: {os.path.basename(out_json)}")

        except Exception as e:
            print(f"  ❌ Error {date_str}: {e}")

if __name__ == "__main__":
    process_s2_area_music()
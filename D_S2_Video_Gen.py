# -*- coding: utf-8 -*-
"""
V3_4_S2_Video_Visualizer_Final_Layout.py
- [Fix] Layout Overlap Issue:
  1. Legend Box Width Increased
  2. Bar Width Reduced
  3. Text-to-Bar Spacing Increased (Prevent overlapping)
- [Update] Visualization Labels: Vegetation, Buildings, Waterbody (% Display)
- [Fix] Path/Compatibility Patches included
"""

import os
import sys
import glob
import json
import numpy as np
import warnings

# =============================================================================
# FluidSynth 경로 패치 (DLL 문제 방지)
# =============================================================================
try:
    current_dir = os.getcwd()
    if hasattr(os, 'add_dll_directory'):
        try: os.add_dll_directory(current_dir)
        except: pass
    os.environ['PATH'] += ';' + current_dir
    original_add = os.add_dll_directory
    def safe_add(path):
        try: return original_add(path)
        except: return None
    os.add_dll_directory = safe_add
except: pass

import rasterio
from rasterio.enums import Resampling
from PIL import Image, ImageDraw, ImageFont
import pretty_midi
from scipy.io import wavfile

if hasattr(os, 'add_dll_directory'): os.add_dll_directory = original_add

try:
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips, VideoFileClip
except ImportError:
    try:
        from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips, VideoFileClip
    except:
        sys.exit()

# =============================================================================
# 설정
# =============================================================================
BASE_DIR = os.getcwd()
RAW_S2_DIR = os.path.join(BASE_DIR, "raw_data", "Sentinel-2")
MIDI_DIR = os.path.join(BASE_DIR, "processed_data", "Daily_MIDI")
JSON_DIR = os.path.join(BASE_DIR, "processed_data", "Daily_Music_Scores") 
OUT_VIDEO_DIR = os.path.join(BASE_DIR, "processed_data", "SatMusic_Videos_Viz")
TMP_DIR = os.path.join(BASE_DIR, "processed_data", "temp_viz")

os.makedirs(OUT_VIDEO_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)
SOUND_FONT_PATH = os.path.join(BASE_DIR, "FluidR3_GM.sf2") 
VIDEO_W, VIDEO_H = 1920, 1080
FPS = 24

# 계절 테마
SEASON_THEME = {
    "Spring": (144, 238, 144),
    "Summer": (34, 139, 34),
    "Autumn": (205, 92, 92),
    "Winter": (135, 206, 235)
}

def get_season_info(date_str):
    month = int(date_str[4:6])
    if 3 <= month <= 5: return "Spring"
    elif 6 <= month <= 8: return "Summer"
    elif 9 <= month <= 11: return "Autumn"
    else: return "Winter"

# MoviePy Helper
def mp_set_audio(clip, audio):
    if hasattr(clip, "with_audio"): return clip.with_audio(audio)
    elif hasattr(clip, "set_audio"): return clip.set_audio(audio)
    else: clip.audio = audio; return clip

def mp_write_file(clip, filename, fps):
    try: clip.write_videofile(filename, fps=fps, codec="libx264", audio_codec="aac", logger=None)
    except: clip.write_videofile(filename, fps=fps, codec="libx264", audio_codec="aac")

# 배경 생성
def create_true_color_bg(date_str, output_img_path):
    folders = glob.glob(os.path.join(RAW_S2_DIR, f"*{date_str}*"))
    if not folders: return False
    target_folder = folders[0]
    def find_band(b): return (glob.glob(os.path.join(target_folder, "**", f"*{b}*.tif"), recursive=True) or [None])[0]
    b4, b3, b2 = find_band("B04"), find_band("B03"), find_band("B02")
    if not (b4 and b3 and b2): return False
    try:
        with rasterio.open(b4) as r, rasterio.open(b3) as g, rasterio.open(b2) as b:
            H, W = r.shape
            sf = max(W, H) / 2000.0
            nh, nw = int(H/sf), int(W/sf)
            red = r.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(float)
            grn = g.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(float)
            blu = b.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(float)
            rgb = np.dstack((red, grn, blu))
            vm = (rgb > 0).any(axis=2)
            if vm.sum() > 0:
                p2, p98 = np.percentile(rgb[vm], (2, 98))
                if (p98-p2)>1e-12: rgb = np.clip((rgb-p2)/(p98-p2),0,1)
            Image.fromarray((rgb*255).astype(np.uint8)).save(output_img_path)
            return True
    except: return False

def create_gradient_bg(date_str, output_path):
    s = get_season_info(date_str)
    c = SEASON_THEME[s]
    arr = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for y in range(1080):
        r = y / 1080
        arr[y, :, 0] = int(100*(1-r) + c[0]*r)
        arr[y, :, 1] = int(100*(1-r) + c[1]*r)
        arr[y, :, 2] = int(100*(1-r) + c[2]*r)
    Image.fromarray(arr).save(output_path)
    return True

# 오디오 합성
def synthesize_midi_high_quality(midi_path, wav_path):
    pm = pretty_midi.PrettyMIDI(midi_path)
    if os.path.exists(SOUND_FONT_PATH):
        try:
            audio_data = pm.fluidsynth(fs=44100, sf2_path=SOUND_FONT_PATH)
            m = np.max(np.abs(audio_data))
            if m > 0: audio_data = audio_data/m * 0.9
            wavfile.write(wav_path, 44100, audio_data.astype(np.float32))
            return True
        except: pass
    try:
        audio_data = pm.synthesize(fs=44100)
        m = np.max(np.abs(audio_data))
        if m > 0: audio_data = audio_data/m * 0.9
        wavfile.write(wav_path, 44100, audio_data.astype(np.float32))
        return True
    except: return False

# =============================================================================
# 시각화 클래스 (레이아웃 수정됨)
# =============================================================================
class DataVisualizer:
    def __init__(self, bg_path, json_path, duration, date_str, season):
        self.bg_base = Image.new("RGB", (VIDEO_W, VIDEO_H), (0, 0, 0))
        src = Image.open(bg_path).convert("RGB")
        sw, sh = src.size
        r = min(VIDEO_W/sw, VIDEO_H/sh)
        nw, nh = int(sw*r), int(sh*r)
        self.paste_x, self.paste_y = (VIDEO_W-nw)//2, (VIDEO_H-nh)//2
        self.img_w, self.img_h = nw, nh
        self.bg_base.paste(src.resize((nw, nh), Image.LANCZOS), (self.paste_x, self.paste_y))
        
        with open(json_path, 'r') as f: self.data = json.load(f)
        self.total_steps = len(self.data)
        self.duration = duration
        self.date_str = date_str
        self.season = season
        try:
            self.font_Title = ImageFont.truetype("arial.ttf", 60)
            self.font_L = ImageFont.truetype("arial.ttf", 40)
            self.font_S = ImageFont.truetype("arial.ttf", 24)
        except:
            self.font_Title = ImageFont.load_default()
            self.font_L = ImageFont.load_default()
            self.font_S = ImageFont.load_default()

    def make_frame(self, t):
        if hasattr(t, "__len__"): 
             try: t = float(t)
             except: t = t[0]

        img = self.bg_base.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        
        prog = np.clip(t / self.duration if self.duration > 0 else 0, 0, 1)
        
        # 스캔라인
        sx = self.paste_x + int(self.img_w * prog)
        draw.line([(sx, self.paste_y), (sx, self.paste_y + self.img_h)], fill=(255, 50, 50, 200), width=4)
        
        # 데이터 가져오기
        idx = int(prog * (self.total_steps - 1))
        step = self.data[idx]
        vis = step.get("visuals", {})
        
        p_veg   = vis.get("pct_veg", 0.0)
        p_build = vis.get("pct_build", 0.0)
        p_water = vis.get("pct_water", 0.0)

        # ★ [수정] 패널 위치와 크기 조정
        # 기존: width 350px (너무 좁음) -> 수정: width 450px
        panel_w = 500
        panel_h = 350
        px = VIDEO_W - panel_w - 50 # 우측에서 50px 띄우고 시작
        py = VIDEO_H - panel_h - 50
        
        draw.rectangle([(px, py), (VIDEO_W-50, VIDEO_H-50)], fill=(0, 0, 0, 180), outline=(255, 255, 255, 100))
        draw.text((px+30, py+20), f"Scan Progress: {int(prog*100)}%", font=self.font_S, fill="white")
        
        # ★ [수정] 바 차트 레이아웃
        def draw_bar(label, val, y, c):
            # 1. 텍스트 라벨 (Vegetation 등)
            draw.text((px+30, y), label, font=self.font_S, fill="white")
            
            # 2. 바 시작 위치를 더 오른쪽으로 이동 (글자와 겹침 방지)
            bar_start_x = px + 200 
            
            # 3. 바 너비 줄이기 (박스 밖으로 나감 방지)
            # 기존 250 -> 180으로 축소
            max_bar_w = 180 
            
            fill_w = int(np.clip(val, 0, 1.0) * max_bar_w)
            bar_h = 20
            
            # 바 배경/채우기
            draw.rectangle([(bar_start_x, y+5), (bar_start_x+max_bar_w, y+5+bar_h)], outline="gray", width=1)
            draw.rectangle([(bar_start_x, y+5), (bar_start_x+fill_w, y+5+bar_h)], fill=c)
            
            # 4. 수치 텍스트 (바 뒤에 표시)
            # 잘리지 않게 위치 계산
            num_x = bar_start_x + max_bar_w + 15
            draw.text((num_x, y), f"{val*100:.1f}%", font=self.font_S, fill=c)

        draw_bar("Vegetation", p_veg,   py+80,  (100, 255, 100))
        draw_bar("Buildings",  p_build, py+140, (255, 100, 100))
        draw_bar("Waterbody",  p_water, py+200, (100, 200, 255))
        
        # 좌측 상단 텍스트
        sc = SEASON_THEME[self.season]
        fmt_date = f"{self.date_str[:4]}-{self.date_str[4:6]}-{self.date_str[6:]}"
        draw.text((50, 50), fmt_date, font=self.font_Title, fill="white", stroke_width=2, stroke_fill="black")
        draw.text((50, 120), self.season, font=self.font_L, fill=sc, stroke_width=1, stroke_fill="black")

        return np.array(img)

def generate_visualized_movie():
    json_files = glob.glob(os.path.join(JSON_DIR, "*.json"))
    if not json_files: print("❌ Run V3_1 first."); return
    json_files.sort(key=lambda f: os.path.basename(f).split("_")[0])
    clips = []
    
    print(">>> Video Gen: Final Layout Fix...")
    for jpath in json_files:
        d = os.path.basename(jpath).split("_")[0]
        s = get_season_info(d)
        print(f"\n🎬 [{d}] ({s})...")
        
        bp = os.path.join(TMP_DIR, f"bg_{d}.png")
        if not os.path.exists(bp):
            if not create_true_color_bg(d, bp): create_gradient_bg(d, bp)
        
        mp = os.path.join(MIDI_DIR, f"{d}_Music_Score.mid")
        wp = os.path.join(TMP_DIR, f"{d}.wav")
        if not os.path.exists(mp): continue
        synthesize_midi_high_quality(mp, wp)
        
        try:
            ac = AudioFileClip(wp)
            dur = ac.duration
            viz = DataVisualizer(bp, jpath, dur, d, s)
            vc = VideoClip(viz.make_frame, duration=dur)
            vc = mp_set_audio(vc, ac)
            vc.fps = FPS
            out = os.path.join(OUT_VIDEO_DIR, f"Viz_{d}.mp4")
            mp_write_file(vc, out, FPS)
            print(f"  ✅ Saved: {out}")
            clips.append(VideoFileClip(out))
        except Exception as e: print(f"  ❌ Err: {e}")

    if clips:
        print("\n🎞️ Concatenating...")
        fp = os.path.join(OUT_VIDEO_DIR, "Seoul_Sentinel2_Symphony_Viz_Layout.mp4")
        try:
            fin = concatenate_videoclips(clips, method="compose")
            mp_write_file(fin, fp, FPS)
            print(f"🎉 Final: {fp}")
        except Exception as e: print(f"Concat Err: {e}")

if __name__ == "__main__":
    generate_visualized_movie()
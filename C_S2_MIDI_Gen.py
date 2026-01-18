# -*- coding: utf-8 -*-
import os
import glob
import json
import numpy as np
import random
from midiutil import MIDIFile

BASE_DIR = os.getcwd()
INPUT_SCORE_DIR = os.path.join(BASE_DIR, "processed_data", "Daily_Music_Scores")
OUT_MIDI_DIR = os.path.join(BASE_DIR, "processed_data", "Daily_MIDI")
os.makedirs(OUT_MIDI_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────
# 1. 설정
# ──────────────────────────────────────────────────────────
SCALE = [
    48, 51, 53, 54, 55, 58,       # C3 (Low)
    60, 63, 65, 66, 67, 70,       # C4 (Mid)
    72, 75, 77, 78, 79, 82,       # C5 (High)
    84, 87, 89, 90, 91, 94        # C6 (Top)
]

INSTRUMENTS = {
    "piano": 0, "guitar": 29, "pad": 90
}
DRUM_CH = 9
TEMPO = 112

# ──────────────────────────────────────────────────────────
# 2. 드럼 패턴 정의
# ──────────────────────────────────────────────────────────
DRUM_PATTERNS = {
    "basic": [ 
        [1,3], [3], [2,3], [3], [1,3], [3], [2,3], [3],
        [1,3], [3], [2,3], [3], [1,3], [3], [2,3], [3]
    ],
    "groove": [ 
        [1,3], [3], [2,3], [1], [3], [1,3], [2,3], [3],
        [1,3], [3], [2,3], [1], [3], [1], [2,3], [3]
    ],
    "break": [ 
        [1,3], [2], [3], [2], [1,3], [2], [3], [2],
        [1,3], [3], [2,3], [1], [1,3], [2], [3], [4]
    ]
}

# ──────────────────────────────────────────────────────────
# 3. 지능형 로직 클래스 (Brain)
# ──────────────────────────────────────────────────────────
class MelodyBrain:
    def __init__(self, name, history_len=6):
        self.name = name
        self.history = []
        self.history_len = history_len
        self.last_note = None

    def get_note(self, z_score, scale_mode="mid"):
        norm = np.clip((z_score + 2.0) / 4.0, 0.0, 1.0)
        
        if scale_mode == "low": s_min, s_max = 0, 12
        elif scale_mode == "high": s_min, s_max = 12, len(SCALE)-1
        else: s_min, s_max = 6, 18
            
        target_idx = int(s_min + norm * (s_max - s_min))
        target_idx = np.clip(target_idx, 0, len(SCALE) - 1)

        is_boring = False
        if len(self.history) >= 4:
            if len(set(self.history[-4:])) <= 2: is_boring = True
        
        if is_boring:
            jump = random.choice([2, 4, 7, -5]) 
            target_idx = np.clip(target_idx + jump, 0, len(SCALE) - 1)
        elif target_idx == self.last_note:
            target_idx += 1 if random.random() > 0.5 else -1
            
        target_idx = np.clip(target_idx, 0, len(SCALE) - 1)
        note = SCALE[target_idx]
        self.last_note = target_idx
        self.history.append(target_idx)
        if len(self.history) > self.history_len: self.history.pop(0)
            
        return note, is_boring

class DrumBrain:
    def __init__(self):
        self.bar_count = 0
        self.current_pattern_name = "basic"
        self.step_in_bar = 0
        
        # ★ 심벌 회피 기동 (Cooldown)
        self.crash_cooldown = 0 
    
    def get_beat(self, step_idx, data_intensity):
        self.step_in_bar = step_idx % 16
        
        # 쿨다운 감소
        if self.crash_cooldown > 0:
            self.crash_cooldown -= 1
        
        if self.step_in_bar == 0 and step_idx > 0:
            self.bar_count += 1
            if self.bar_count % 4 == 0:
                if data_intensity > 0.5: self.current_pattern_name = "break"
                elif data_intensity > 0.2: self.current_pattern_name = "groove"
                else: self.current_pattern_name = "basic"
        
        if (self.bar_count + 1) % 4 == 0 and self.step_in_bar >= 12:
            return self.generate_fill_in(self.step_in_bar)
            
        return DRUM_PATTERNS[self.current_pattern_name][self.step_in_bar]

    def generate_fill_in(self, step_in_bar):
        if step_in_bar == 12: return [2] 
        if step_in_bar == 13: return [2] 
        if step_in_bar == 14: return [1, 2] 
        if step_in_bar == 15: return [4] 
        return []
    
    # ★ 크래쉬 요청 처리 함수
    def try_crash(self):
        # 쿨다운이 0일 때만 발사
        if self.crash_cooldown == 0:
            self.crash_cooldown = 32 # 2마디(32 steps) 동안 다시 울리지 않음
            return True
        return False

# ──────────────────────────────────────────────────────────
# 4. 유틸리티
# ──────────────────────────────────────────────────────────
def map_vol(val, boost=False):
    base = 85 if boost else 65
    return int(np.clip(base + val * 40, 0, 127))

def humanize(vol):
    if vol == 0: return 0
    change = random.randint(-8, 8)
    return int(np.clip(vol + change, 1, 127))

# ──────────────────────────────────────────────────────────
# 5. 메인 변환
# ──────────────────────────────────────────────────────────
def convert_s2_midi_final():
    json_files = glob.glob(os.path.join(INPUT_SCORE_DIR, "*.json"))
    
    if not json_files:
        print("No JSON files found.")
        return

    for jpath in json_files:
        try:
            with open(jpath, 'r') as f:
                data = json.load(f)
            
            mid = MIDIFile(4) 
            mid.addTempo(0, 0, TEMPO)
            
            mid.addProgramChange(0, 0, 0, INSTRUMENTS["piano"]) 
            mid.addProgramChange(1, 1, 1, INSTRUMENTS["guitar"])
            mid.addProgramChange(2, 2, 2, INSTRUMENTS["pad"])
            
            brain_piano = MelodyBrain("Piano")
            brain_guitar = MelodyBrain("Guitar")
            brain_drum = DrumBrain()
            
            t = 0
            step_dur = 0.25
            
            for i, step_data in enumerate(data):
                r = step_data.get("rhythm", {})
                m = step_data.get("melody", {})
                
                # -------------------------------------------------
                # 1. DRUM
                # -------------------------------------------------
                avg_intensity = (r.get("kick",0) + r.get("snare",0) + r.get("hihat",0)) / 3.0
                drum_hits = brain_drum.get_beat(i, avg_intensity)
                
                for hit_type in drum_hits:
                    if hit_type == 1: 
                        vol = 80 + int(r.get("kick", 0)*40)
                        mid.addNote(3, DRUM_CH, 36, t, step_dur, humanize(vol))
                    elif hit_type == 2: 
                        vol = 90 + int(r.get("snare", 0)*30)
                        mid.addNote(3, DRUM_CH, 38, t, step_dur, humanize(vol))
                    elif hit_type == 3: 
                        mid.addNote(3, DRUM_CH, 42, t, step_dur, humanize(60))
                    elif hit_type == 4: 
                        mid.addNote(3, DRUM_CH, 46, t, step_dur, humanize(85))

                # ★ 심벌(Crash) 회피 기동 적용
                # hihat 값(실제로는 NDWI/물)이 높으면 크래쉬 시도
                if r.get("hihat", 0) > 0.4:
                    if brain_drum.try_crash(): # 쿨다운 체크
                        mid.addNote(3, DRUM_CH, 49, t, step_dur, 110) # Crash!

                # -------------------------------------------------
                # 2. MELODY
                # -------------------------------------------------
                if "ndvi" in m:
                    z = m["ndvi"].get("zscore", 0.0)
                    v = m["ndvi"].get("vol", 0.0)
                    if v > 0.0:
                        note, bored = brain_piano.get_note(z, "mid")
                        if not (bored and random.random() < 0.2):
                            mid.addNote(0, 0, note, t, step_dur, humanize(map_vol(v, bored)))

                if "ndbi" in m:
                    z = m["ndbi"].get("zscore", 0.0)
                    v = m["ndbi"].get("vol", 0.0)
                    if v > 0.0:
                        note, bored = brain_guitar.get_note(z, "low")
                        if i % 2 == 0:
                            mid.addNote(1, 1, note, t, step_dur * 2, humanize(map_vol(v)))

                # NDWI (Water) -> Pad
                # JSON 키가 'ndwi'로 바뀌었을 수 있으므로 체크 (혹은 기존 ndmi 키 사용시 호환)
                pad_key = "ndwi" if "ndwi" in m else "ndmi"
                if pad_key in m:
                    v = m[pad_key].get("vol", 0.0)
                    if v > 0.0:
                        mid.addNote(2, 2, 60, t, step_dur * 4, humanize(int(50 + v*30)))

                t += step_dur
            
            out_name = os.path.basename(jpath).replace(".json", ".mid")
            out_path = os.path.join(OUT_MIDI_DIR, out_name)
            with open(out_path, "wb") as f:
                mid.writeFile(f)
            print(f"Generated MIDI: {out_name} (Crash Cooldown Applied)")
            
        except Exception as e:
            print(f"Error {jpath}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    convert_s2_midi_final()
# SatOrchestra Sonification Seoul 🛰️🎹
Sonification of Seoul using Sentinel-2 imagery

## Overview
This project generates an audio-visual symphony of Seoul from satellite imagery.  
Using **Sentinel-2**, we analyze vegetation, urban density, and water bodies, then transform them into musical instruments (Piano, Guitar, Pad) and rhythm using Python.

## 📺 Preview
- YouTube: TODO (paste your link here)

## 🛠️ How it works
1. **Data Acquisition (`A_S2_download.py`)**
   - Downloads Sentinel-2 imagery for Seoul (Spring, Summer, Autumn, Winter).
2. **Analysis (`B_S2_JSON_Gen.py`)**
   - Calculates NDVI (Vegetation), NDBI (Urban), and NDWI (Water) indices.
3. **Sonification (`C_S2_MIDI_Gen.py`)**
   - **Vegetation** → Piano 🎹 (Pitch mapped by Z-score)
   - **Buildings/Urban** → Electric Guitar 🎸
   - **Water** → Ambient Pad 🌊
   - **Rhythm** → Generated based on data intensity changes
4. **Visualization (`D_S2_Video_Gen.py`)**
   - Creates a video with a moving scanline and data gauges, then merges with synthesized audio.

## 📦 Requirements & Setup (Important!)

### 1) Python packages
Install dependencies via `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2) System dependency: FFmpeg (required for video rendering)
MoviePy requires **FFmpeg** to render MP4.

- Windows (Chocolatey):
```bash
choco install ffmpeg
```
- macOS (Homebrew):
```bash
brew install ffmpeg
```
- Ubuntu/Debian:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

### 3) Seoul boundary file (GeoJSON) (⚠️ required)
This project needs a Seoul boundary GeoJSON to define the ROI (region of interest).

- File name: `Seoul.geojson`
- Action: Place `Seoul.geojson` in the **project root directory** (same level as the scripts).

Notes:
- This repository does **NOT** include `Seoul.geojson`. You must obtain it yourself.
- The GeoJSON should contain a valid polygon/multipolygon boundary for Seoul.
- If the boundary file is missing, ROI-based cropping/masking will fail.

### 4) SoundFont (.sf2) file (⚠️ required for high-quality audio)
This project uses FluidSynth + SoundFont to generate high-quality instrument sounds.  
SoundFont files are not included due to file size limits.

- Recommended: **FluidR3_GM.sf2** (approx. 140MB)
- Action: Download the `.sf2` file and place it in the **project root directory**.

Note:
- If no SoundFont is found, the code may fall back to low-quality synthesis.

## 🚀 Usage
Run the scripts in alphabetical order:

### A) Download Sentinel-2 imagery
```bash
python A_S2_download.py
```
- Output: `raw_data/`

### B) Analyze imagery and generate score JSON
```bash
python B_S2_JSON_Gen.py
```
- Output: `processed_data/Daily_Music_Scores/`

### C) Convert score JSON to MIDI
```bash
python C_S2_MIDI_Gen.py
```
- Output: `processed_data/Daily_MIDI/`

### D) Synthesize audio and render the final video
```bash
python D_S2_Video_Gen.py
```
- Output: `processed_data/SatMusic_Videos_Viz/`

## Project structure (example)
- `A_S2_download.py`
- `B_S2_JSON_Gen.py`
- `C_S2_MIDI_Gen.py`
- `D_S2_Video_Gen.py`
- `Seoul.geojson` (required, user-provided)
- `FluidR3_GM.sf2` (optional but recommended, user-provided)
- `raw_data/` (generated)
- `processed_data/` (generated)

## Troubleshooting
- Video export fails:
  - Ensure **FFmpeg** is installed and accessible in PATH.
- Low-quality or missing audio:
  - Confirm `FluidR3_GM.sf2` is in the project root.

## License
TODO (MIT / Apache-2.0 / etc.)

## Author
Created by djkwon85

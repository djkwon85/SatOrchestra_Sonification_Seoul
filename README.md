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
   - Creates a video with a moving scanline and data gauges

## 📦 Requirements & Setup (Important!)
### 1) Python libraries
Install required packages:
```bash
pip install rasterio moviepy pretty_midi scipy pystac_client pyfluidsynth
```

### 2) SoundFont (.sf2) file (⚠️ required for high-quality audio)
This project uses FluidSynth to generate high-quality instrument sounds.  
You MUST download a SoundFont file manually (not included due to file size limits).

- Recommended: **FluidR3_GM.sf2** (approx. 140MB)
- Action: Download the `.sf2` file and place it in the **root directory** of this project.

Note: If no SoundFont is found, the code may fall back to low-quality sine waves.

### 3) Seoul boundary file (GeoJSON) (⚠️ required)
A Seoul administrative boundary file is required to define the region of interest (ROI).

- File: `Seoul.geojson`
- Action: Place `Seoul.geojson` in the **root directory** of this project (same level as the scripts).

Notes:
- The GeoJSON should contain a valid polygon/multipolygon boundary for Seoul.
- If the boundary file is missing, ROI-based cropping/masking will fail.

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
- Output: `processed_data/`

### C) Convert score JSON to MIDI
```bash
python C_S2_MIDI_Gen.py
```
- Output: MIDI files (path depends on your script settings)

### D) Synthesize audio and render the final video
```bash
python D_S2_Video_Gen.py
```
- Output: final video (path depends on your script settings)

## Author
Created by djkwon85

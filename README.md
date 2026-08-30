# 🎙️ Subtitle AI — Real-Time Streaming Video Subtitle Generator

> Watch any video on any website and get automatically generated subtitles in real time with synchronized timing, customizable typography, and low-latency Whisper ASR.

---

## 🏗️ Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│                   BROWSER EXTENSION                    │
│                                                        │
│  Active Tab (<video>)         Offscreen Audio Streamer │
│  ┌──────────────────────┐     ┌──────────────────────┐ │
│  │  Content Script      │     │  chrome.tabCapture   │ │
│  │  - Video Detector    │     │  - 16kHz Mono PCM    │ │
│  │  - Subtitle Overlay  │     │  - WebSocket Stream  │ │
│  └──────────▲───────────┘     └──────────┬───────────┘ │
└─────────────┼────────────────────────────┼─────────────┘
              │ Subtitle Cues              │ Binary Audio Frames
              │ (JSON)                     │ (PCM 16-bit 16kHz)
┌─────────────┴────────────────────────────▼─────────────┐
│                    FASTAPI BACKEND                     │
│                                                        │
│  WebSocket Handler (/ws/transcribe/{sessionId})        │
│    │                                                   │
│    ├──► Silero VAD (Speech vs Silence Segmentation)    │
│    │                                                   │
│    ├──► faster-whisper (Persistent Model in VRAM/RAM)  │
│    │      - Word Timestamps & Confidence Scores        │
│    │                                                   │
│    ├──► Subtitle Engine                                │
│    │      - 2 Lines Max, ~40-42 Chars/Line             │
│    │      - CPS Reading Speed Bounds                   │
│    │      - Natural Punctuation & Pause Splitting      │
│    │                                                   │
│    └──► Session & Timestamp Clock Synchronizer         │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart Guide

### 1. Start the ASR Backend Server

Ensure Python 3.9+ is installed, then run:

```bash
cd backend
pip install -r requirements.txt
python main.py
```

The server will start at `http://127.0.0.1:8000` (WebSocket endpoint: `ws://127.0.0.1:8000/ws/transcribe/{sessionId}`).
Verify server health at `http://127.0.0.1:8000/health`.

---

### 2. Load the Chrome Extension (Manifest V3)

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Turn on the **Developer mode** toggle in the top-right corner.
3. Click the **Load unpacked** button in the top-left.
4. Select the `extension/` directory from this repository.
5. The **Subtitle AI** extension icon will now appear in your browser toolbar!

---

### 3. Verify with the Verification Testbed Player

1. Open `demo-player/index.html` in your browser.
2. Click the **Subtitle AI** extension icon in your Chrome toolbar.
3. In the extension popup:
   - Verify connection status shows **Ready** or **Connected**.
   - Select spoken language (or leave as **Auto Detect**).
   - Click **Generate Subtitles**.
4. In the testbed player, click **"Speak Dialogue"** or **"Play Continuous Track"**.
5. Subtitles will appear overlaid directly above the video player in real time!

---

## 🎨 Subtitle Customization & Styling

Subtitle AI comes with a built-in appearance customization engine:

### Presets
- **Netflix Style**: Modern yellow/white text with semi-transparent dark box & rounded corners.
- **Classic**: White text with solid dark text outline and transparent background.
- **High Contrast**: High visibility yellow text on 95% black background.
- **Large & Accessible**: Extra large text with thick outline.

### Custom Controls
- **Font Size**: Adjustable from `14px` to `38px`.
- **Text Color**: Live color picker + quick swatches (White, Yellow, Cyan, Neon Green).
- **Background Opacity**: Adjustable from `0%` (transparent) to `100%` (solid).
- **Text Outlines**: `None`, `Thin`, `Medium`, `Thick`.
- **Screen Position**: `Bottom`, `Above Bottom`, `Center`, `Top`.
- **Timing Offset Calibration**: `[-] 0.5s [+]` manual sync adjuster to compensate for audio lag or browser clock differences.

---

## 📁 Repository Structure

```text
├── backend/
│   ├── main.py              # FastAPI server & lifespan coordinator
│   ├── websocket.py         # Streaming binary WebSocket audio handler
│   ├── vad.py               # Voice Activity Detection (Silero VAD)
│   ├── asr.py               # faster-whisper worker & model manager
│   ├── subtitles.py         # Subtitle formatting & CPS pacing engine
│   ├── sessions.py          # Session timestamp sync & audio buffer state
│   ├── requirements.txt     # Backend Python dependencies
│   └── test_client.py       # Simulated streaming test client
│
├── extension/
│   ├── manifest.json        # Chrome Extension Manifest V3 configuration
│   ├── background/
│   │   └── service-worker.js# Capture coordinator & offscreen manager
│   ├── content/
│   │   ├── video-detector.js# Detects <video> elements & tracks currentTime
│   │   ├── overlay.js       # Dynamic subtitle DOM renderer & style engine
│   │   └── styles.css       # Subtitle overlay styling
│   ├── offscreen/
│   │   ├── audio-capture.html
│   │   └── audio-capture.js # 16kHz mono downsampler & WebSocket client
│   ├── popup/
│   │   ├── index.html       # Popup user interface
│   │   ├── popup.js         # Controls, offset stepper & preset controller
│   │   └── styles.css       # Popup dark-mode styles
│   ├── shared/
│   │   └── settings.js      # Subtitle preset schemas & storage helpers
│   └── icons/
│       └── icon.svg         # Extension vector branding
│
└── demo-player/
    └── index.html           # Local standalone HTML5 verification player
```

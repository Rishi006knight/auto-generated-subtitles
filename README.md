# 🎙️ Subtitle AI — Production Real-Time Streaming Subtitle Generator

> Watch any video on any website and get automatically generated subtitles in real time with synchronized timing, customizable typography, low-latency Whisper ASR, and **Smart Auto-Pause**.

---

## 🚀 Key Production Features & Improvements

- **⏸️ Smart Auto-Pause (Anti-Desync Buffer)**: Eliminates subtitle desynchronization. If the backend ASR worker queue experiences lag (queue depth &ge; 3), the backend emits `lag_warning`. The extension seamlessly pauses the `<video>` element and shows an elegant `⏳ Syncing subtitles...` toast. Once the queue clears, the backend emits `lag_clear`, the video automatically resumes, and subtitles stay in 100% lockstep!
- **⚡ Client-Side VAD & Silence Gating**: The extension computes RMS audio energy in the offscreen document and suppresses streaming during background silence or music, saving bandwidth and backend GPU compute.
- **🛡️ Whisper Hallucination Defense**: Filters hallucinated segments (`no_speech_prob > 0.6`, `avg_logprob < -1.0`, repetition compression ratio anomalies, and known phantom text loops).
- **🖥️ Fullscreen Trap Fix**: Automatically detects `fullscreenchange` and reparents the subtitle overlay into `document.fullscreenElement` so subtitles remain on top in true fullscreen mode.
- **✨ Anti-Flicker Partial Buffering**: Debounces rapid partial updates (120ms buffer) and maps cues by `chunk_id` for seamless in-place text updates without DOM reflow jitter.
- **🔒 Thread & Coroutine Safe**: Uses `asyncio.Lock()` inference mutex to support multiple concurrent client tabs without VRAM/memory corruption.
- **🔄 Rolling Acoustic Context Buffer**: Pre-rolls 1.0s of previous audio context so Whisper doesn't lose acoustic continuity between consecutive speech segments.
- **⏱️ Ping/Pong Latency Calibration**: Dynamically measures network RTT and compensates subtitle display timestamps.
- **🐳 Docker & GPU Ready**: Production `Dockerfile` and `docker-compose.yml` with CUDA 12.1 + PyTorch + faster-whisper.
- **📦 TypeScript + Vite Tooling**: Build pipeline with `@crxjs/vite-plugin` for Hot Module Reloading (HMR) and Manifest V3 compilation.

---

## 🏗️ Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│                   BROWSER EXTENSION                    │
│                                                        │
│  Active Tab (<video>)         Offscreen Audio Streamer │
│  ┌──────────────────────┐     ┌──────────────────────┐ │
│  │  Content Script      │     │  chrome.tabCapture   │ │
│  │  - Video Detector    │     │  - Client-Side VAD   │ │
│  │  - Smart Auto-Pause  │◄────┤  - 16kHz Mono PCM    │ │
│  │  - Fullscreen Reparent     │  - Ping/Pong Latency │ │
│  │  - Anti-Flicker Buff │     │  - Control Msg Relay │ │
│  └──────────▲───────────┘     └──────────┬───────────┘ │
└─────────────┼────────────────────────────┼─────────────┘
              │ Subtitle Cues (JSON)       │ Binary Audio Frames
              │ Control (lag_warning/clear)│ (Speech only)
┌─────────────┴────────────────────────────▼─────────────┐
│                    FASTAPI BACKEND                     │
│                                                        │
│  WebSocket Handler (/ws/transcribe/{sessionId})        │
│    │                                                   │
│    ├──► Session Queue Manager & Lag Monitor            │
│    │      (Emits lag_warning / lag_clear)              │
│    │                                                   │
│    ├──► Silero VAD (Server Speech Segmentation)        │
│    │                                                   │
│    ├──► faster-whisper Worker (asyncio.Lock Mutex)     │
│    │      - Hallucination Filter (no_speech_prob)      │
│    │      - Word Timestamps & Confidence Scores        │
│    │                                                   │
│    ├──► Subtitle Engine                                │
│    │      - 2 Lines Max, ~40-42 Chars/Line             │
│    │      - CPS Reading Speed Bounds                   │
│    │      - Chunk ID Mapping                           │
│    │                                                   │
│    └──► Rolling Buffer & Latency Compensator           │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ Quickstart Guide

### 1. Start Backend (Local or Docker)

#### Local Python:
```bash
cd backend
pip install -r requirements.txt
python main.py
```

#### Or with Docker (GPU-accelerated):
```bash
cd backend
docker compose up --build
```

---

### 2. Build & Load Chrome Extension

```bash
cd extension
npm install
npm run build
```

1. Open Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select the `extension/` (or `extension/dist`) folder.

---

### 3. Verify with the Verification Testbed

1. Open `demo-player/index.html` in Chrome.
2. Click the **Subtitle AI** extension icon in your Chrome toolbar.
3. Verify that **Smart Auto-Pause** toggle is enabled.
4. Select your preferred style preset (**Netflix**, **Classic**, **High Contrast**, **Accessible**, or **Custom**).
5. Click **Generate Subtitles**.
6. Click **"Speak Dialogue"** in the testbed player to watch real-time synchronized subtitles appear over the video!

---

### 4. Run Benchmark & WER Evaluation

```bash
python backend/test_client.py
```
This streams synthetic audio to the backend and evaluates Word Error Rate (WER) and Ping/Pong RTT latency.

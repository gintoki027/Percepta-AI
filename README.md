<div align="center">

# Percepta-AI 🦯


_An AI-powered assistive navigation system that enables visually impaired users to perceive and interact with their surroundings through real-time object detection, depth estimation, text recognition, and intelligent audio feedback._

</div>

---

##  Table of Contents

- [Features](#-features)
- [Tech Stack](#️-tech-stack)
- [Architecture](#-architecture)
- [Folder Structure](#-folder-structure)
- [Feature Details](#-feature-details)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Mobile Usage](#-mobile-usage)
- [Deployment](#-deployment)
- [Screenshots](#-screenshots)
- [Contributors](#-contributors)
- [Future Scope](#-future-scope)

---

## ✨ Features

| Category | Highlights |
|---|---|
| **Object Detection** | Real-time YOLOv8 detection with distance estimation and directional alerts |
| **Depth Estimation** | MiDaS-powered monocular depth to judge how close objects are |
| **Scene Description** | Full scene narration via Qwen2-VL vision-language model |
| **OCR / Sign Reading** | EasyOCR reads street signs, labels, and notices aloud |
| **Voice Output** | Browser-native TTS (Web Speech API) with configurable speech speed |
| **Haptic Feedback** | Vibration API alerts for dangerously close objects |
| **Object Finder** | On-demand search for a specific object in the camera view |
| **PWA** | Installable Progressive Web App — works offline for app shell |

---

## 🛠️ Tech Stack

### Frontend

| Technology | Purpose |
|---|---|
| **HTML5 / CSS3 / Vanilla JS** | UI — no framework required |
| **Web Speech API** | Browser-native text-to-speech output |
| **Vibration API** | Haptic alerts for nearby obstacles |
| **MediaDevices API** | Camera access (front / rear) |
| **WebSocket** | Real-time bidirectional frame streaming |
| **Service Worker** | PWA offline caching |
| **Canvas API** | Detection bounding-box overlay rendering |

### Backend

| Technology | Purpose |
|---|---|
| **Python 3.10+** | Language runtime |
| **FastAPI** | Async REST + WebSocket server |
| **Uvicorn** | ASGI server |
| **YOLOv8 (Ultralytics)** | Real-time object detection |
| **MiDaS (timm)** | Monocular depth estimation |
| **EasyOCR** | Optical character recognition for signs |
| **Qwen2-VL (HF API / Ollama)** | Vision-language model for scene description |
| **OpenCV** | Frame decoding and image processing |
| **python-dotenv** | Environment variable management |

---

## 🏗️ Architecture

```
Browser (any device)           Python Backend (FastAPI)
├── Camera capture      ←WS→   ├── YOLOv8 detection
├── Web Speech TTS              ├── MiDaS depth estimation
├── Haptic vibration            ├── Object tracking
└── Settings UI                 └── Qwen2-VL scene summary (via HF API)
Browser (any device)                  Python Backend (FastAPI)
├── Camera capture (MediaDevices)      ├── /ws/stream  — WebSocket frame handler
├── Canvas overlay (bounding boxes)    │     ├── YOLOv8  object detection
├── Web Speech API (TTS)    ←─WS─→    │     ├── MiDaS   depth estimation
├── Vibration API (haptics)            │     ├── SimpleTracker  object tracking
├── PWA / Service Worker               │     └── EasyOCR  sign reading
└── Settings UI                        ├── POST /api/describe-scene — VLM narration
                                       ├── POST /api/read-signs     — OCR endpoint
                                       └── GET  /api/health         — health check
```

## Quick Start
---

##  Folder Structure

```
Percepta-AI-web/
├── frontend/                        # Vanilla HTML/CSS/JS Progressive Web App
│   ├── index.html                   # App shell & UI layout
│   ├── manifest.json                # PWA manifest (icons, theme, display mode)
│   ├── sw.js                        # Service worker for offline caching
│   ├── serve_https.py               # Helper: serve over HTTPS for mobile camera
│   ├── css/
│   │   └── style.css                # All app styles (dark theme, responsive)
│   ├── js/
│   │   └── app.js                   # App logic: WebSocket, TTS, haptics, overlay
│   └── icons/                       # PWA icon assets (192×192, 512×512)
│
├── backend/                         # FastAPI Python backend
│   ├── main.py                      # App entry point: routes, WebSocket handler
│   ├── config.py                    # Config from env vars with defaults
│   ├── requirements.txt             # Python dependencies
│   ├── .env.example                 # Environment variable template
│   └── models/
│       ├── detector.py              # YOLOv8 object detection wrapper
│       ├── depth.py                 # MiDaS depth estimator
│       ├── tracker.py               # Simple centroid-based object tracker
│       ├── scene_describer.py       # Generates directional spoken alerts
│       ├── ocr_reader.py            # EasyOCR sign-reading with cooldown
│       └── vlm_service.py           # VLM adapter (Hugging Face or Ollama)
│
├── .gitignore
└── README.md
```

---

##  Feature Details

###  Real-Time Object Detection & Distance Alerts

- **YOLOv8 nano** runs on every camera frame streamed via WebSocket.
- Detected objects are filtered to a curated list of navigation-critical items (people, cars, bicycles, doors, etc.).
- **MiDaS** estimates depth every 6th frame (cached between runs) to approximate distance in metres.
- Objects closer than the configured threshold trigger a spoken alert and haptic vibration.
- Directional labels (left / centre / right) are calculated from the bounding-box position.

###  Scene Description (VLM)

- On demand (or at a configurable interval), a full camera frame is sent to a vision-language model.
- **Qwen2-VL-2B** (via Hugging Face Inference API) or a local **Ollama** model generates a short, navigation-focused scene summary.
- The description is read aloud via the Web Speech API.

###  OCR Sign Reading

- **EasyOCR** scans the frame every N frames (configurable) for readable text.
- Detected signs are filtered by confidence and minimum text length, then announced with a cooldown to avoid repetition.
- Results are overlaid on the canvas and spoken aloud.

###  Haptic Feedback

- Uses the browser **Vibration API** to pulse the device when an object is detected within close range.
- Works on Android and supported mobile browsers.

###  Find Object Mode

- The user can request the assistant to search for a specific object (e.g., "chair", "door").
- The backend highlights only that object class and provides directional guidance until found.

### 1. Install dependencies
###  Progressive Web App (PWA)

- Installable from the browser on Android and desktop.
- Service worker caches the app shell for instant loading and limited offline use.

---

##  Getting Started

### Prerequisites

| Tool | Version |
|---|---|
| **Python** | 3.10+ |
| **pip** | Latest |
| **Node.js** | Not required (vanilla JS frontend) |

### 1 — Clone the repository

```bash
git clone https://github.com/MiniPro-IV-syntax-squad/Percepta-AI-web.git
cd Percepta-AI-web
```

### 2 — Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure
> **GPU users:** Install the CUDA-enabled PyTorch build first for significantly faster inference:
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```
### 3 — Configure environment variables
```bash
cp .env.example .env
# Edit .env and add your Hugging Face API token:
# HF_API_TOKEN=hf_xxxxxxxxxxxxx
cp backend/.env.example backend/.env
# Edit backend/.env and fill in your values (see Environment Variables section)
```
Get your free token at: https://huggingface.co/settings/tokens

### 3. Run
### 4 — Run the server

```bash
cd backend
python main.py
```

Open **http://localhost:8000** in any browser.
Open **http://localhost:8000** in any browser. The frontend is served automatically by FastAPI.

---

##  Environment Variables

Create a `.env` file inside the **`backend/`** directory (or copy `.env.example`):

### 4. Mobile Usage
| Variable | Description | Default |
|---|---|---|
| `VLM_PROVIDER` | VLM backend — `huggingface`, `ollama`, or `none` | `huggingface` |
| `HF_API_TOKEN` | Hugging Face Inference API token | _(required for HF)_ |
| `HF_MODEL_ID` | HF model ID for scene description | `Qwen/Qwen2-VL-2B-Instruct` |
| `OLLAMA_BASE_URL` | Ollama server URL (if using local VLM) | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `qwen2-vl` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `YOLO_MODEL` | YOLOv8 model file | `yolov8n.pt` |
| `DETECTION_CONFIDENCE` | Minimum detection confidence (0–1) | `0.5` |
| `MAX_ANNOUNCE_DISTANCE` | Max distance (m) for spoken alerts | `3.0` |
| `OCR_ENABLED` | Enable/disable EasyOCR sign reading | `true` |
| `OCR_FRAME_INTERVAL` | Run OCR every N frames | `10` |
| `OCR_COOLDOWN` | Seconds before re-announcing the same sign | `15` |
| `ANNOUNCE_COOLDOWN` | Seconds before re-announcing the same object | `8` |

1. Ensure phone and server are on the **same network**
2. Open `http://<your-pc-ip>:8000` on your phone
3. Grant camera permission → tap  to start
> Get a free Hugging Face token at: https://huggingface.co/settings/tokens
> **Note:** For HTTPS (required for camera on remote mobile), use a reverse proxy like ngrok: `ngrok http 8000`
---

## Features
##  Mobile Usage

| Feature | Technology |
|---------|-----------|
| Object detection | YOLOv8 nano |
| Depth estimation | MiDaS small |
| Scene description | Qwen2-VL-2B (HF API) |
| Voice output | Web Speech API (browser TTS) |
| Haptic alerts | Vibration API |
| Camera | MediaDevices API |
| Streaming | WebSocket |
1. Ensure your phone and server are on the **same Wi-Fi network**.
2. Open `http://<your-pc-ip>:8000` on your phone.
3. Grant camera permission → tap  to start.

## Deployment
> **HTTPS for mobile camera access:**  
> Most mobile browsers require HTTPS to access the camera on non-localhost origins.  
> Use the bundled HTTPS helper or ngrok:
> ```bash
> # Option A — self-signed certificate (already bundled in /frontend)
> python frontend/serve_https.py
>
> # Option B — ngrok tunnel
> ngrok http 8000
> ```
For production deployment, use a cloud server with GPU for faster inference:
---
##  Deployment
```bash
# Using ngrok for quick public URL
ngrok http 8000
# Development — auto-reload
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# Production — multiple workers
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
# Or deploy on a cloud VM with GPU
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Cloud VM with GPU (recommended for faster inference)
# Install CUDA PyTorch first, then run the above
```
---
<!-- 
## 📸 Screenshots

### Main Camera View
_(screenshot placeholder)_

### Detection Overlay
_(screenshot placeholder)_

### Scene Description
_(screenshot placeholder)_

### Settings Panel
_(screenshot placeholder)_

---


## 🔭 Future Scope

| Feature | Description |
|---|---|
| **GPS Integration** | Combine object detection with GPS for turn-by-turn navigation |
| **Obstacle Avoidance** | Predict walking path obstructions and suggest detours |
| **Multi-language OCR** | Detect and read signs in regional languages |
| **On-device Inference** | Run YOLOv8 + depth in the browser via ONNX / WebNN |
| **Custom Object Training** | Fine-tune the detector on user-specific important objects |
| **Wearable Support** | Integrate with smart glasses or bone-conduction headsets |
| **Cloud Sync** | Save detection logs and scene history to the cloud |
README.md

copilot/feature-imp -->

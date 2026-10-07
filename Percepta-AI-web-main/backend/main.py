"""
Blind Helper — FastAPI Backend Server

Serves the frontend and provides:
- WebSocket /ws/stream  — real-time frame processing (detection + depth)
- POST    /api/describe-scene — VLM scene summarization
- GET     /api/health — health check
"""

import asyncio
import base64
import io
import json
import time
import traceback

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image

import config
from models.detector import ObjectDetector
from models.depth import DepthEstimator
from models.tracker import SimpleTracker
from models.scene_describer import SceneDescriber
from models.vlm_service import create_vlm_service
from models.ocr_reader import OCRReader

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(title="Blind Helper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global model instances (loaded once at startup) ─────────────────
detector: ObjectDetector = None
depth_estimator: DepthEstimator = None
vlm_service = None
scene_describer: SceneDescriber = None
ocr_reader: OCRReader = None


@app.on_event("startup")
async def load_models():
    """Load ML models into memory at server startup."""
    global detector, depth_estimator, vlm_service, scene_describer, ocr_reader
    print("=" * 60)
    print("  Blind Helper — Loading models...")
    print("=" * 60)

    detector = ObjectDetector()
    depth_estimator = DepthEstimator()
    vlm_service = create_vlm_service()
    scene_describer = SceneDescriber()

    if config.OCR_ENABLED:
        ocr_reader = OCRReader()
    else:
        print("[OCR] Disabled via config")

    print("=" * 60)
    print("  All models loaded. Server ready.")
    print("=" * 60)


# ── Helpers ──────────────────────────────────────────────────────────
def decode_frame(data: str) -> np.ndarray:
    """Decode a base64 JPEG/PNG string to a BGR numpy frame."""
    # Strip data URI prefix if present
    if "," in data:
        data = data.split(",", 1)[1]

    img_bytes = base64.b64decode(data)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return frame


def frame_to_bytes(frame: np.ndarray) -> bytes:
    """Encode a BGR frame to JPEG bytes."""
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes()


# ── WebSocket: Real-time frame processing ────────────────────────────
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Receives base64-encoded camera frames.
    Returns JSON with detection results, messages, and overlay data.
    """
    await websocket.accept()
    print("[WS] Client connected")

    tracker = SimpleTracker(max_distance=config.TRACKER_MAX_DISTANCE)
    describer = SceneDescriber()
    frame_count = 0
    cached_depth_map = None
    cached_ocr_overlay = []  # persist OCR overlay across non-OCR frames
    last_frame_time = 0

    try:
        while True:
            # Receive frame as base64 string
            try:
                data = await websocket.receive_text()
            except RuntimeError:
                break  # WebSocket already closed

            try:
                # ── Frame skipping: discard stale frames ──
                now = time.time()
                if (now - last_frame_time) < 0.1:
                    # Less than 100ms since last processed frame — skip
                    # (prevents queue buildup when processing is slow)
                    continue
                last_frame_time = now

                frame = decode_frame(data)
                if frame is None:
                    await websocket.send_json({"error": "Invalid image data"})
                    continue

                start_time = time.time()
                frame_count += 1

                # ── Parallel pipeline: run YOLO + Depth + OCR concurrently ──
                # Build list of tasks to run in parallel
                tasks = []

                # Task 0: YOLO detection (always)
                tasks.append(asyncio.to_thread(detector.detect, frame))

                # Task 1: Depth estimation (every 6th frame for CPU efficiency)
                run_depth = (cached_depth_map is None or frame_count % 6 == 0)
                if run_depth:
                    tasks.append(asyncio.to_thread(depth_estimator.estimate, frame))

                # Task 2: OCR (every N frames)
                run_ocr = (ocr_reader and frame_count % config.OCR_FRAME_INTERVAL == 0)
                if run_ocr:
                    tasks.append(asyncio.to_thread(ocr_reader.read_signs, frame))

                # Run all tasks in parallel
                results = await asyncio.gather(*tasks)

                # Unpack results
                idx = 0
                detections = results[idx]; idx += 1

                if run_depth:
                    cached_depth_map = results[idx]; idx += 1
                depth_map = cached_depth_map

                ocr_detections = []
                if run_ocr:
                    ocr_detections = results[idx]; idx += 1

                # ── Post-processing (fast, no need to parallelize) ──
                # Track objects
                tracked = tracker.update(detections)

                # Generate descriptions
                messages, overlay_data = describer.describe(
                    tracked, depth_map, frame.shape[1]
                )

                # Process OCR results
                ocr_messages = []
                if run_ocr:
                    ocr_messages = ocr_reader.filter_new_signs(
                        ocr_detections, frame.shape[1]
                    )
                    # Update cached OCR overlay
                    cached_ocr_overlay = [
                        {
                            "text": det["text"],
                            "bbox": det["bbox"],
                            "center": det["center"],
                            "confidence": det["confidence"]
                        }
                        for det in ocr_detections
                    ]

                process_time = round((time.time() - start_time) * 1000)

                # Send results (always include cached OCR overlay)
                response = {
                    "messages": messages,
                    "overlay": overlay_data,
                    "ocr_texts": ocr_messages,
                    "ocr_overlay": cached_ocr_overlay,
                    "process_time_ms": process_time,
                    "frame_width": frame.shape[1],
                    "frame_height": frame.shape[0]
                }
                await websocket.send_json(response)

            except Exception as e:
                traceback.print_exc()
                try:
                    await websocket.send_json({"error": str(e)})
                except RuntimeError:
                    pass  # Client already disconnected

    except WebSocketDisconnect:
        print("[WS] Client disconnected")


# ── REST: VLM Scene Description ─────────────────────────────────────
@app.post("/api/describe-scene")
async def describe_scene_endpoint(file: UploadFile = File(...)):
    """
    Accepts an image file.
    Returns a natural language scene description from the VLM.
    """
    try:
        image_bytes = await file.read()
        description = await vlm_service.describe_scene(image_bytes)
        return {"description": description}
    except Exception as e:
        traceback.print_exc()
        return {"description": f"Error: {str(e)}"}


# ── REST: OCR Sign Reading ──────────────────────────────────────────
@app.post("/api/read-signs")
async def read_signs_endpoint(file: UploadFile = File(...)):
    """
    Accepts an image file.
    Returns all text detected via OCR with positions.
    """
    try:
        if not ocr_reader:
            return {"texts": [], "error": "OCR is disabled"}

        image_bytes = await file.read()
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if frame is None:
            return {"texts": [], "error": "Invalid image"}

        detections = ocr_reader.read_signs(frame)
        messages = ocr_reader.filter_new_signs(detections, frame.shape[1])

        return {"texts": detections, "messages": messages}
    except Exception as e:
        traceback.print_exc()
        return {"texts": [], "error": str(e)}


@app.post("/api/describe-scene-base64")
async def describe_scene_base64(data: dict):
    """
    Accepts a JSON body with {"image": "<base64 string>"}.
    Alternative to file upload for easier frontend integration.
    """
    try:
        img_data = data.get("image", "")
        if "," in img_data:
            img_data = img_data.split(",", 1)[1]

        image_bytes = base64.b64decode(img_data)
        description = await vlm_service.describe_scene(image_bytes)
        return {"description": description}
    except Exception as e:
        traceback.print_exc()
        return {"description": f"Error: {str(e)}"}


# ── Health Check ─────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "models": {
            "detector": detector is not None,
            "depth": depth_estimator is not None,
            "vlm": vlm_service is not None,
            "ocr": ocr_reader is not None
        }
    }


# ── Serve Frontend Static Files ─────────────────────────────────────
import os

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    # Serve css/, js/, icons/ at root-relative paths (no /static prefix)
    css_path = os.path.join(frontend_path, "css")
    js_path = os.path.join(frontend_path, "js")
    icons_path = os.path.join(frontend_path, "icons")

    if os.path.exists(css_path):
        app.mount("/css", StaticFiles(directory=css_path), name="css")
    if os.path.exists(js_path):
        app.mount("/js", StaticFiles(directory=js_path), name="js")
    if os.path.exists(icons_path):
        app.mount("/icons", StaticFiles(directory=icons_path), name="icons")

    # Keep /static mount for backward compatibility
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/manifest.json")
    async def serve_manifest():
        return FileResponse(os.path.join(frontend_path, "manifest.json"))

    @app.get("/sw.js")
    async def serve_sw():
        return FileResponse(os.path.join(frontend_path, "sw.js"))


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import socket

    # Check for SSL certificates (for mobile camera access over HTTPS)
    cert_file = os.path.join(frontend_path, "cert.pem")
    key_file = os.path.join(frontend_path, "key.pem")

    ssl_kwargs = {}
    if os.path.exists(cert_file) and os.path.exists(key_file):
        ssl_kwargs["ssl_certfile"] = cert_file
        ssl_kwargs["ssl_keyfile"] = key_file
        protocol = "https"
    else:
        protocol = "http"

    # Get local IP for display
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    print(f"\n{'='*50}")
    print(f"  Open on your phone:")
    print(f"  {protocol}://{local_ip}:{config.PORT}")
    print(f"{'='*50}\n")

    uvicorn.run(app, host=config.HOST, port=config.PORT, **ssl_kwargs)

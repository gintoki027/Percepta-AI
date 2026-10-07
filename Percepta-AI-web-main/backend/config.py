"""
Configuration for Blind Helper backend.
Uses environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# --- VLM Provider ---
# Options: "huggingface", "ollama", "none"
VLM_PROVIDER = os.getenv("VLM_PROVIDER", "huggingface")

# Hugging Face
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct")

# Ollama (fallback)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2-vl")

# --- Detection ---
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.5"))

# Important objects to announce
IMPORTANT_OBJECTS = [
    "person", "car", "bicycle", "chair", "dog", "truck", "bus",
    "motorcycle", "cat", "bench", "fire hydrant", "stop sign",
    "traffic light", "backpack", "umbrella", "handbag", "suitcase",
    "skateboard", "potted plant", "dining table", "door"
]

# --- Depth / Distance ---
MAX_ANNOUNCE_DISTANCE = float(os.getenv("MAX_ANNOUNCE_DISTANCE", "3.0"))  # meters

# --- Tracking ---
TRACKER_MAX_DISTANCE = float(os.getenv("TRACKER_MAX_DISTANCE", "120"))  # pixels
TRACKER_MAX_DISAPPEARED = int(os.getenv("TRACKER_MAX_DISAPPEARED", "3"))  # frames before dropping

# --- Detection Filtering ---
MIN_BBOX_SIZE = int(os.getenv("MIN_BBOX_SIZE", "30"))  # minimum bbox width/height in pixels

# --- Announcement ---
ANNOUNCE_COOLDOWN = float(os.getenv("ANNOUNCE_COOLDOWN", "8"))  # seconds between re-announcing same object
MAX_MESSAGES_PER_FRAME = int(os.getenv("MAX_MESSAGES_PER_FRAME", "2"))  # max spoken alerts per frame
DISTANCE_CHANGE_THRESHOLD = float(os.getenv("DISTANCE_CHANGE_THRESHOLD", "1"))  # meters change before re-announce

# --- Streaming ---
DEFAULT_FPS = int(os.getenv("DEFAULT_FPS", "2"))

# --- VLM Scene Description ---
VLM_PROMPT = """This image is from a camera used by a visually impaired person.

Describe the scene from the camera wearer's perspective.

Focus only on objects relevant for navigation and safety.

Mention:
- objects ahead, left, and right
- moving objects (cars, bicycles, people)
- obstacles in the walking path

Use short phrases.

Example format:
person ahead
car approaching from left
bicycle on right
clear path forward"""

# --- OCR (Sign Board Reading) ---
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "en").split(",")
OCR_CONFIDENCE = float(os.getenv("OCR_CONFIDENCE", "0.4"))
OCR_MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "2"))
OCR_FRAME_INTERVAL = int(os.getenv("OCR_FRAME_INTERVAL", "10"))  # run OCR every N frames
OCR_COOLDOWN = float(os.getenv("OCR_COOLDOWN", "15"))  # seconds before re-announcing same text

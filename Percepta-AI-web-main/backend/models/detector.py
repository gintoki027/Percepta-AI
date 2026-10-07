"""
YOLOv8 Object Detection wrapper.
Filters detections by confidence, minimum size, and important objects.
"""

import torch
from ultralytics import YOLO
import config


class ObjectDetector:
    """Wraps YOLOv8 for object detection with smart filtering."""

    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Detector] Loaded YOLOv8 on {self.device}")

    def detect(self, frame):
        """
        Run detection on a BGR frame.
        Returns list of dicts: [{"label": str, "center": (cx, cy), "bbox": (x1,y1,x2,y2), "confidence": float}]
        Filters out:
          - Detections below confidence threshold
          - Bounding boxes smaller than MIN_BBOX_SIZE
          - Objects not in the IMPORTANT_OBJECTS list
        """
        results = self.model(frame, conf=config.DETECTION_CONFIDENCE, verbose=False)
        detections = []

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                label = self.model.names[cls]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # Filter: minimum bounding box size
                bbox_w = x2 - x1
                bbox_h = y2 - y1
                if bbox_w < config.MIN_BBOX_SIZE or bbox_h < config.MIN_BBOX_SIZE:
                    continue

                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                detections.append({
                    "label": label,
                    "center": (cx, cy),
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "confidence": round(conf, 2)
                })

        return detections

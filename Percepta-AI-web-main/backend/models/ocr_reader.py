"""
OCR Reader — EasyOCR-based text recognition for sign boards and instruction boards.

Reads text from camera frames and filters for navigation-relevant signs.
Uses cooldown logic to avoid repeating the same sign text.
"""

import time
import numpy as np
import cv2
import torch
import config


class OCRReader:
    """Reads text from camera frames using EasyOCR."""

    def __init__(self):
        import easyocr
        use_gpu = torch.cuda.is_available()
        self.reader = easyocr.Reader(
            config.OCR_LANGUAGES,
            gpu=use_gpu,
            verbose=False
        )
        # Track announced signs: {normalized_text: last_announced_timestamp}
        self.announced_signs = {}
        self.is_cpu = not use_gpu

        # Histogram-based scene change detection for OCR caching
        self._last_histogram = None
        self._cached_detections = []
        self._similarity_threshold = 0.85  # skip OCR if scene is >85% similar

        print(f"[OCR] Loaded EasyOCR on {'GPU' if use_gpu else 'CPU'} for languages: {config.OCR_LANGUAGES}")
        if self.is_cpu:
            print(f"[OCR] CPU mode: frames will be downscaled for speed")

    def _compute_histogram(self, frame):
        """Compute a normalized grayscale histogram for scene comparison."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)
        return hist

    def _scene_changed(self, frame):
        """Check if the scene has changed enough to warrant re-running OCR."""
        current_hist = self._compute_histogram(frame)
        if self._last_histogram is None:
            self._last_histogram = current_hist
            return True

        similarity = cv2.compareHist(
            self._last_histogram, current_hist, cv2.HISTCMP_CORREL
        )
        if similarity < self._similarity_threshold:
            self._last_histogram = current_hist
            return True
        return False

    def read_signs(self, frame):
        """
        Run OCR on a BGR frame.

        Returns list of dicts:
        [
            {
                "text": str,
                "confidence": float,
                "bbox": [x1, y1, x2, y2],
                "center": [cx, cy]
            },
            ...
        ]

        Applies filtering:
        - Scene change detection (returns cached results if scene is similar)
        - Minimum text length
        - Minimum confidence threshold
        - Minimum bounding box area (filters tiny noise text)
        """
        # Scene change check — return cached results if camera barely moved
        if not self._scene_changed(frame):
            return self._cached_detections
        # Downscale on CPU for much faster OCR (signs are large text, still readable)
        h, w = frame.shape[:2]
        scale = 1.0
        max_dim = 640 if self.is_cpu else 1280
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        # Convert BGR to RGB for EasyOCR
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Run OCR detection + recognition
        results = self.reader.readtext(rgb_frame)

        detections = []
        for (bbox_points, text, confidence) in results:
            # Filter by confidence
            if confidence < config.OCR_CONFIDENCE:
                continue

            # Filter by text length
            text = text.strip()
            if len(text) < config.OCR_MIN_TEXT_LENGTH:
                continue

            # Convert bbox points to x1, y1, x2, y2
            # EasyOCR returns [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            x1, y1 = int(min(xs)), int(min(ys))
            x2, y2 = int(max(xs)), int(max(ys))

            # Filter by minimum bounding box area (ignore tiny text)
            bbox_area = (x2 - x1) * (y2 - y1)
            if bbox_area < 800:  # roughly 30x27 pixels minimum
                continue

            # Scale coordinates back to original frame size
            if scale < 1.0:
                inv = 1.0 / scale
                x1, y1 = int(x1 * inv), int(y1 * inv)
                x2, y2 = int(x2 * inv), int(y2 * inv)

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            detections.append({
                "text": text,
                "confidence": round(confidence, 2),
                "bbox": [x1, y1, x2, y2],
                "center": [cx, cy]
            })

        self._cached_detections = detections
        return detections

    def filter_new_signs(self, detections, frame_width):
        """
        Filter OCR detections to only include signs that haven't been
        recently announced. Returns list of message strings.

        Args:
            detections: list from read_signs()
            frame_width: width of the frame for position mapping

        Returns:
            list of message strings to speak, e.g. ["Sign reads: No Entry, ahead"]
        """
        messages = []
        now = time.time()

        for det in detections:
            text = det["text"]
            normalized = text.lower().strip()

            # Check cooldown — skip if recently announced
            last_time = self.announced_signs.get(normalized, 0)
            if (now - last_time) < config.OCR_COOLDOWN:
                continue

            # Determine spatial position
            cx = det["center"][0]
            pos = self._get_position(cx, frame_width)

            # Build message
            msg = f"Sign reads: {text}, {pos}"
            messages.append(msg)

            # Record announcement time
            self.announced_signs[normalized] = now

        # Clean up old entries (older than 2x cooldown)
        cutoff = now - (config.OCR_COOLDOWN * 2)
        self.announced_signs = {
            k: v for k, v in self.announced_signs.items() if v > cutoff
        }

        return messages

    def _get_position(self, x, frame_width):
        """5-zone spatial position from x coordinate (same as SceneDescriber)."""
        ratio = x / frame_width
        if ratio < 0.15:
            return "far left"
        elif ratio < 0.35:
            return "on your left"
        elif ratio < 0.65:
            return "ahead"
        elif ratio < 0.85:
            return "on your right"
        else:
            return "far right"

    def reset(self):
        """Clear announced signs history and caches."""
        self.announced_signs.clear()
        self._last_histogram = None
        self._cached_detections = []

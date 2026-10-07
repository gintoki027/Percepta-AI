"""
Scene description generator.
Combines object detection + depth to produce spatial navigation messages.

Smart announcement logic:
- Announce each object only ONCE when it first appears
- Re-announce ONLY on significant events (danger zone, large distance change)
- Cooldown timer prevents re-announcing within ANNOUNCE_COOLDOWN seconds
- Max MAX_MESSAGES_PER_FRAME spoken alerts per frame
- 5-zone directional guidance (far left / left / ahead / right / far right)
- Region-based depth sampling (median of bbox) for accuracy
- Approaching/receding notifications
"""

import time
import math
import numpy as np
import config


class SceneDescriber:
    """Generates navigation-relevant text descriptions from detections + depth."""

    def __init__(self):
        # Track: {object_id: {"last_announced": timestamp, "last_distance": float, "danger_announced": bool}}
        self.tracked_state = {}
        self.previous_ids = set()

    def _get_position(self, x, frame_width):
        """5-zone spatial position from x coordinate."""
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

    def _estimate_distance(self, obj, depth_map):
        """
        Estimate distance using median depth within the bounding box region.
        More accurate than single center-pixel sampling.
        """
        h, w = depth_map.shape[:2]
        depth_min = depth_map.min()
        depth_max = depth_map.max()

        bbox = obj.get("bbox")
        if bbox:
            x1, y1, x2, y2 = bbox
            # Clamp to frame bounds
            x1 = max(0, min(x1, w - 1))
            x2 = max(0, min(x2, w - 1))
            y1 = max(0, min(y1, h - 1))
            y2 = max(0, min(y2, h - 1))

            if x2 > x1 and y2 > y1:
                region = depth_map[y1:y2, x1:x2]
                depth_val = float(np.median(region))
            else:
                cx, cy = obj["center"]
                depth_val = depth_map[min(cy, h - 1), min(cx, w - 1)]
        else:
            cx, cy = obj["center"]
            depth_val = depth_map[min(cy, h - 1), min(cx, w - 1)]

        depth_norm = (depth_val - depth_min) / (depth_max - depth_min + 1e-6)
        raw_distance = float((1 - depth_norm) * 5)
        return max(1, round(raw_distance))

    def describe(self, tracked_objects, depth_map, frame_width):
        """
        Generate spoken descriptions for tracked objects.

        Args:
            tracked_objects: dict from tracker {id: {"label", "center", ...}}
            depth_map: 2D numpy array from MiDaS
            frame_width: width of the frame in pixels

        Returns:
            (messages, overlay_data) — list of strings and list of dicts for frontend
        """
        messages = []
        overlay_data = []
        current_ids = set()
        now = time.time()

        # Process all objects and build overlay + candidate messages
        candidates = []

        for oid, obj in tracked_objects.items():
            label = obj["label"]
            x, y = obj["center"]
            current_ids.add(oid)

            # Estimate distance using region-based depth
            est_distance = self._estimate_distance(obj, depth_map)

            # 5-zone position
            pos = self._get_position(x, frame_width)

            # Build overlay data (always shown visually)
            overlay_item = {
                "id": oid,
                "label": label,
                "center": [int(x), int(y)],
                "distance": est_distance,
                "position": pos,
                "bbox": obj.get("bbox"),
                "important": label in config.IMPORTANT_OBJECTS
            }
            overlay_data.append(overlay_item)

            # --- Smart announcement logic ---
            if label not in config.IMPORTANT_OBJECTS:
                continue
            if est_distance > config.MAX_ANNOUNCE_DISTANCE:
                continue

            obj_state = self.tracked_state.get(oid)

            if obj_state is None:
                # NEW object — announce it
                if est_distance == 1:
                    msg = f"{label} {est_distance} meter {pos}"
                else:
                    msg = f"{label} {est_distance} meters {pos}"

                candidates.append((est_distance, msg))
                self.tracked_state[oid] = {
                    "last_announced": now,
                    "last_distance": est_distance,
                    "danger_announced": est_distance <= 1
                }
            else:
                # EXISTING object — check for re-announcement triggers
                last_time = obj_state.get("last_announced", 0)
                last_dist = obj_state.get("last_distance", est_distance)
                was_danger = obj_state.get("danger_announced", False)
                is_danger = est_distance <= 1
                cooldown_ok = (now - last_time) >= config.ANNOUNCE_COOLDOWN
                dist_changed = abs(est_distance - last_dist) >= config.DISTANCE_CHANGE_THRESHOLD

                # Trigger 1: Entered danger zone
                if is_danger and not was_danger:
                    msg = f"Warning! {label} very close, {pos}!"
                    candidates.append((est_distance, msg))
                    obj_state["danger_announced"] = True
                    obj_state["last_announced"] = now

                # Trigger 2: Approaching (distance decreased significantly) + cooldown passed
                elif est_distance < last_dist and dist_changed and cooldown_ok:
                    msg = f"{label} approaching, {est_distance} meters {pos}"
                    candidates.append((est_distance, msg))
                    obj_state["last_announced"] = now

                # Update state
                if not is_danger:
                    obj_state["danger_announced"] = False
                obj_state["last_distance"] = est_distance

        # Sort by distance (closest first) and limit messages
        candidates.sort(key=lambda c: c[0])
        for _, msg in candidates[:config.MAX_MESSAGES_PER_FRAME]:
            messages.append(msg)

        # Clean up tracked state for objects that left the frame
        gone_ids = self.previous_ids - current_ids
        for gone_id in gone_ids:
            self.tracked_state.pop(gone_id, None)

        self.previous_ids = current_ids

        return messages, overlay_data

    def reset(self):
        """Clear all tracked state."""
        self.tracked_state.clear()
        self.previous_ids.clear()

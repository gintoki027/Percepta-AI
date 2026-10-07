"""
Centroid-based object tracker with persistence.
Objects survive brief detection gaps (max_disappeared frames)
to prevent flickering announcements.
"""

from scipy.spatial import distance
import config


class SimpleTracker:
    """
    Track objects across frames using centroid distance matching.
    Assigns persistent IDs and keeps objects alive for a few missed frames.
    """

    def __init__(self, max_distance=None, max_disappeared=None):
        self.objects = {}          # id -> detection dict
        self.disappeared = {}      # id -> count of frames since last seen
        self.next_id = 0
        self.max_distance = max_distance or config.TRACKER_MAX_DISTANCE
        self.max_disappeared = max_disappeared or config.TRACKER_MAX_DISAPPEARED

    def update(self, detections):
        """
        Match new detections against existing tracked objects.
        Objects persist for max_disappeared frames without a match before removal.

        Args:
            detections: list of dicts with at least "label" and "center" keys.
        Returns:
            dict mapping object_id -> detection dict (includes stale objects)
        """
        # If no detections, increment disappeared count for all
        if len(detections) == 0:
            for oid in list(self.disappeared.keys()):
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_disappeared:
                    del self.objects[oid]
                    del self.disappeared[oid]
            return self.objects

        # Match detections to existing objects
        new_objects = {}
        used_ids = set()
        unmatched_dets = []

        for det in detections:
            center = det["center"]
            label = det["label"]
            matched_id = None
            min_dist = 1e9

            for oid, obj in self.objects.items():
                if oid in used_ids:
                    continue
                # Only match objects with the same label
                if obj.get("label") != label:
                    continue
                dist = distance.euclidean(center, obj["center"])
                if dist < min_dist and dist < self.max_distance:
                    min_dist = dist
                    matched_id = oid

            if matched_id is not None:
                used_ids.add(matched_id)
                new_objects[matched_id] = det
                self.disappeared[matched_id] = 0  # reset disappearance counter
            else:
                unmatched_dets.append(det)

        # Register unmatched detections as new objects
        for det in unmatched_dets:
            new_objects[self.next_id] = det
            self.disappeared[self.next_id] = 0
            self.next_id += 1

        # Increment disappeared count for unmatched existing objects
        for oid in list(self.objects.keys()):
            if oid not in used_ids:
                self.disappeared[oid] = self.disappeared.get(oid, 0) + 1
                if self.disappeared[oid] <= self.max_disappeared:
                    # Keep the stale object with its last known position
                    if oid not in new_objects:
                        new_objects[oid] = self.objects[oid]
                else:
                    # Object truly gone — remove it
                    self.disappeared.pop(oid, None)

        self.objects = new_objects
        return self.objects

    def reset(self):
        """Clear all tracked objects."""
        self.objects = {}
        self.disappeared = {}
        self.next_id = 0

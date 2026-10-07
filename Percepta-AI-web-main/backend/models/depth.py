"""
MiDaS Depth Estimation wrapper.
"""

import cv2
import torch
import numpy as np


class DepthEstimator:
    """Wraps MiDaS for monocular depth estimation."""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
        self.model.to(self.device)
        self.model.eval()

        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        self.transform = midas_transforms.small_transform
        print(f"[Depth] Loaded MiDaS_small on {self.device}")

    def estimate(self, frame):
        """
        Estimate depth from a BGR frame.
        Returns a 2D numpy depth map (same H×W as input).
        Higher values = closer (inverted MiDaS convention).
        """
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_batch = self.transform(img).to(self.device)

        with torch.no_grad():
            prediction = self.model(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()
        return depth_map

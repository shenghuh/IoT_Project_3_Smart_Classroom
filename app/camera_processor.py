"""
camera_processor.py

Reads frames from the laptop webcam and computes an approximate
brightness value (0-255, higher = brighter).
"""

import cv2
import numpy as np


class CameraProcessor:
    def __init__(self, camera_index: int = 0):
        """
        :param camera_index: Index of the webcam (0 is usually the default).
        """
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera index {self.camera_index}")

    def read_brightness(self) -> float:
        """
        Capture a single frame from the camera and return its average brightness
        in the range 0-255 (approx).

        :return: brightness value as float
        """
        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from camera")

        # Convert to grayscale, then take mean value
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        return brightness

    def release(self) -> None:
        """Release the camera resource."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __del__(self):
        self.release()

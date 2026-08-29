import cv2
import numpy as np

class BallastLeakDetector:
    """
    Detects water leak/spray in ballast tank footage using
    motion + brightness/low-saturation intersection (no ML training needed).
    """
    def __init__(self, motion_threshold=4000, spray_pixel_threshold=2000):
        self.prev_gray = None
        self.motion_threshold = motion_threshold
        self.spray_pixel_threshold = spray_pixel_threshold

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.prev_gray is None:
            self.prev_gray = gray
            return None

        # Motion mask
        diff = cv2.absdiff(self.prev_gray, gray)
        _, motion_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        self.prev_gray = gray

        motion_pixels = cv2.countNonZero(motion_mask)
        if motion_pixels < self.motion_threshold:
            return None

        # Spray mask: bright, low-saturation regions (white water/foam)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_spray = np.array([0, 0, 180])
        upper_spray = np.array([180, 60, 255])
        spray_mask = cv2.inRange(hsv, lower_spray, upper_spray)

        # Only count spray pixels that are ALSO moving
        combined = cv2.bitwise_and(motion_mask, spray_mask)
        spray_motion_pixels = cv2.countNonZero(combined)

        if spray_motion_pixels > self.spray_pixel_threshold:
            confidence = min(0.97, 0.55 + spray_motion_pixels / 20000)
            return {
                "category": "Ballast",
                "camera": "Cam 2 - Ballast Room",
                "type": "leak",
                "confidence": round(confidence, 3),
            }
        return None

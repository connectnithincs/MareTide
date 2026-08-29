# calibrate_ballast.py — run standalone, watch printed values, then set real thresholds
import cv2
import numpy as np
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(base_dir, "assets", "ballast", "room_loop.mp4")

cap = cv2.VideoCapture(video_path)
prev_gray = None
frame_idx = 0

print("Scanning ballast room video for motion and spray pixels calibration...")
print("Frame | Motion Pixels | Spray Motion Pixels")
print("-" * 43)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if prev_gray is None:
        prev_gray = gray
        continue

    diff = cv2.absdiff(prev_gray, gray)
    _, motion_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    motion_pixels = cv2.countNonZero(motion_mask)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    spray_mask = cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))
    combined = cv2.bitwise_and(motion_mask, spray_mask)
    spray_motion_pixels = cv2.countNonZero(combined)

    if frame_idx % 10 == 0:
        print(f" {frame_idx:03d}  |    {motion_pixels:6d}   |       {spray_motion_pixels:6d}")
        
    prev_gray = gray
    frame_idx += 1

cap.release()
print("Calibration complete.")

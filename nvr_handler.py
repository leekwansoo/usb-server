# nvr_handler.py
import cv2
import time
import os

class NVRHandler:
    def __init__(self, width=640, height=480, fps=30):
        self.recording = False
        self.writer = None
        self.width = width
        self.height = height
        self.fps = fps

    def start_recording(self):
        if self.recording:
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"record_{timestamp}.mp4"

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(filename, fourcc, self.fps, (self.width, self.height))
        self.recording = True
        print(f"[NVR] Recording started: {filename}")

    def stop_recording(self):
        if not self.recording:
            return

        self.recording = False
        self.writer.release()
        self.writer = None
        print("[NVR] Recording stopped")

    def write_frame(self, frame):
        if self.recording and self.writer is not None:
            self.writer.write(frame)

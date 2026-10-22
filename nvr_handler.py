# nvr_handler.py
import cv2
import time
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

root_dir = Path(__file__).parent
recordings_dir = root_dir / "recordings"
file_path = recordings_dir / "record.mp4"

class NVRHandler:
    def __init__(self, width=640, height=480, fps=30):
        self.recording = False
        self.writer = None
        self.width = width
        self.height = height
        self.fps = fps
        self._lock = threading.Lock()
        self.last_file = None
        self._frames = 0
        self._first_ts = None
        self._last_ts = None

    def start_recording(self):
        with self._lock:
            if self.recording:
                return

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"record_{timestamp}.mp4"

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(str(recordings_dir / filename), fourcc, self.fps, (self.width, self.height))
            self.recording = self.writer.isOpened()
            self.last_file = str(recordings_dir / filename) if self.recording else None
            self._frames = 0
            self._first_ts = None
            self._last_ts = None
            print(f"[NVR] Recording started: {filename}" if self.recording else "[NVR] Failed to open writer")

    def stop_recording(self):
        with self._lock:
            if not self.recording:
                return
            self.recording = False
            self.writer.release()
            self.writer = None
        print("[NVR] Recording stopped")

    def write_frame(self, frame):
        with self._lock:
            if self.recording and self.writer is not None:
                if (frame.shape[1], frame.shape[0]) != (self.width, self.height):
                    frame = cv2.resize(frame, (self.width, self.height))
                self.writer.write(frame)
                now = time.monotonic()
                if self._first_ts is None:
                    self._first_ts = now
                self._last_ts = now
                self._frames += 1

    def add_audio(self, audio_bytes):
        """Mux browser-recorded audio into the last finished recording."""
        with self._lock:
            if self.recording or not self.last_file or not os.path.exists(self.last_file):
                return False, "no finished recording"
            video = self.last_file
            frames, first, last = self._frames, self._first_ts, self._last_ts

        if frames == 0:
            try:
                os.remove(video)
            except OSError:
                pass
            return False, "no video frames were recorded (is a video or camera playing?)"

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False, "ffmpeg not found"

        # Frames arrive slower or faster than the nominal fps, so stretch the video to real time.
        scale = 1.0
        if frames > 1 and last > first:
            real = (last - first) * frames / (frames - 1)
            scale = real / (frames / self.fps)

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.webm")
            out_path = os.path.join(tmp, "out.mp4")
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
            cmd = [
                ffmpeg, "-y", "-i", video, "-i", audio_path,
                "-filter:v", f"setpts=PTS*{scale:.6f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                "-shortest", out_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0 or not os.path.exists(out_path):
                print(result.stderr[-500:])
                return False, "ffmpeg failed"
            shutil.move(out_path, video)
        print(f"[NVR] Audio added: {video}")
        return True, video

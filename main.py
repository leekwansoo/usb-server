# main functions for fastapi server
import cv2
import base64
import asyncio
import datetime
import random
import os
import json
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

CAMERA_RTSP = {
    "Camera1": os.getenv("CAMERA1_RTSP"),
    "Camera2": os.getenv("CAMERA2_RTSP"),
}

from pathlib import Path
from usb_device import list_usb_devices
from nvr_handler import NVRHandler
nvr_handler = NVRHandler()


def _mjpeg_frames(url: str):
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.resize(frame, (640, 360))
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
    finally:
        cap.release()

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

STATE = {
    "Door1": "CLOSED",
    "Door2": "CLOSED",
    "Camera1": {"online": True, "motion": False},
    "Webcam1": {"online": True, "motion": False},
}


# Open your USB webcam
def get_usb_camera_index():
    usb_devices = list_usb_devices()
    if "WEBCAM" in usb_devices:
        return usb_devices.index("WEBCAM")
    else:
        return 0

def get_usb_camera():
    camera_index = get_usb_camera_index()
    camera = cv2.VideoCapture(camera_index)
    return camera
camera = get_usb_camera()

def play_video(video_path):
    cap = cv2.VideoCapture(str(video_path))
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (640, 480))
        cv2.imshow('Video', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()   
    return True

async def webcam_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            success, frame = camera.read()
            if not success:
                await asyncio.sleep(0.05)
                continue

            nvr_handler.write_frame(frame)

            ret, buffer = cv2.imencode(".jpg", frame)
            frame_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
            await websocket.send_text(frame_b64)

            await asyncio.sleep(0.03)
    except (WebSocketDisconnect, RuntimeError):
        # Browser closed or reloaded the page
        pass

async def _webcam_mjpeg():
    while True:
        success, frame = await asyncio.to_thread(camera.read)
        if not success:
            await asyncio.sleep(0.05)
            continue
        nvr_handler.write_frame(frame)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        await asyncio.sleep(0.03)
        
async def tapo_camera_stream(websocket: WebSocket):
    await websocket.accept()
    url = CAMERA_RTSP.get("Camera1")
    if not url:
        await websocket.close(code=1011, reason="CAMERA1_RTSP is not set in .env")
        return

    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    cap = await asyncio.to_thread(cv2.VideoCapture, url, cv2.CAP_FFMPEG)
    try:
        if not cap.isOpened():
            await websocket.close(code=1011, reason="Cannot open Tapo RTSP stream")
            return
        failures = 0
        while True:
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok or frame is None or frame.size == 0:
                failures += 1
                if failures > 50:
                    await websocket.close(code=1011, reason="RTSP stream lost")
                    return
                await asyncio.sleep(0.05)
                continue
            failures = 0
            nvr_handler.write_frame(frame)

            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                continue
            await websocket.send_text(base64.b64encode(buffer.tobytes()).decode("utf-8"))
            await asyncio.sleep(0.01)
    except (WebSocketDisconnect, RuntimeError):
        # Browser closed or reloaded the page
        pass
    finally:
        cap.release()

# websocket = None  # Replace with an actual WebSocket instance before








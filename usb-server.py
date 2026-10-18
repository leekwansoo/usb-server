import cv2
import base64
import asyncio
import datetime
import random
import os
import json
from dotenv import load_dotenv
load_dotenv()

CAMERA_RTSP = {
    "Camera1": os.getenv("CAMERA1_RTSP"),
    "Camera2": os.getenv("CAMERA2_RTSP"),
}
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from usb_device import list_usb_devices
from nvr_handler import NVRHandler
nvr_handler = NVRHandler()
import numpy as np
import os, uuid
from ultralytics import YOLO

from main import _mjpeg_frames, _webcam_mjpeg, play_video, webcam_stream, get_usb_camera_index, get_usb_camera
camera = get_usb_camera()

from main import STATE, STATIC_DIR, BASE_DIR, CAMERA_RTSP, get_usb_camera_index
CAMERA_RTSP = CAMERA_RTSP
BASE_DIR = BASE_DIR
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = STATIC_DIR
STATE = STATE

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Open your USB webcam
usb_devices = list_usb_devices()
if "WEBCAM" in usb_devices:
    camera_index = usb_devices.index("WEBCAM")
else:
    camera_index = 0
print(f"Using camera index: {camera_index}")
camera = cv2.VideoCapture(camera_index)

# websocket = None  # Replace with an actual WebSocket instance before
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/webcam_index")
def get_webcam_index():
    return {"camera_index": camera_index}

@app.get("/webcam")
def index(request: Request):
    return templates.TemplateResponse(request, "webcam-dashboard.html")


@app.get("/api/camera/{camera_id}/stream")
async def api_camera_stream(camera_id: str):
    """[UPLINK] RTSP -> MJPEG stream for browser <img>"""
    url = CAMERA_RTSP.get(camera_id)
    if not url:
        return JSONResponse({"error": f"Set CAMERA1_RTSP/CAMERA2_RTSP env for {camera_id}"}, status_code=404)
    try:
        import cv2  # noqa: F401
    except ImportError:
        return JSONResponse({"error": "opencv-python not installed"}, status_code=500)
    return StreamingResponse(_mjpeg_frames(url), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/webcam/stream")
async def api_webcam_stream(webcam: int = 0):
    """[UPLINK] USB Webcam -> MJPEG stream for browser <img>"""
    if not camera.isOpened():
        return JSONResponse({"error": "Webcam not available"}, status_code=404)
    return StreamingResponse(_webcam_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")
@app.get("/start_recording")
def start_recording():
    nvr_handler.start_recording()
    return {"status": "recording started"}

@app.get("/stop_recording")
def stop_recording():
    nvr_handler.stop_recording()
    return {"status": "recording stopped"}

@app.get("/write_frame")
def write_frame():
    nvr_handler.write_frame()
    return {"status": "frame written"}


# 얼굴용 YOLO 모델 로드 (처음 한번만)
yolo_face = YOLO("yolov8n-face.pt") 
SAVE_DIR = "captures"
os.makedirs(SAVE_DIR, exist_ok=True)

@app.post("/api/camera/{camera_id}/capture")
async def capture_and_recognize(camera_id: str, file: UploadFile = File(...)):
    # 1. JPG 저장
    filename = f"{camera_id}_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(SAVE_DIR, filename)
    
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # 2. YOLO 안면 인식
    results = yolo_face(path, conf=0.5, verbose=False)
    detections = []
    for box in results[0].boxes:
        x1,y1,x2,y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        detections.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": conf, "label": "face"})

    return {"saved": filename, "path": path, "detections": detections, "count": len(detections)}

@app.get("/api/status")
async def api_all_status():
    """[UPLINK] Terminal -> Server : Get all devices status (Both-way demo)"""
    # Simulate temp drift
    STATE["Temp1"]["temperature"] = round(22.5 + random.random()*3.5, 1)
    
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Terminal -> Server (UPLINK)",
        "devices": {
            "Door1": {"status": STATE["Door1"]},
            "Light1": STATE["Light1"],
            "Camera1": {"online": True, "motion": random.choice([True, False]), "recording": True},
            "Webcam1": {"online": True, "motion": random.choice([True, False]), "recording": True},
        }
    }
@app.websocket("/ws/bothway")
async def websocket_bothway(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "type": "UPLINK",
                "timestamp": datetime.datetime.now().isoformat(),
                "Camera1": {"motion": random.choice([True, False])},
                "Webcam1": {"motion": random.choice([True, False])},
                "Switch1": {"power_w": random.randint(800, 1500) if STATE["Switch1"]["state"] == "ON" else 0},
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/video")
async def video_ws(websocket: WebSocket):
    await webcam_stream(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("usb-server:app", host="127.0.0.1", port=8000, reload=True)
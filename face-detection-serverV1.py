# Face Detection Server using FastAPI and YOLO
import json
import os
import asyncio
from random import random
from PIL import Image
import datetime
from dotenv import load_dotenv
load_dotenv()


from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from usb_device import list_usb_devices
from main import get_usb_camera

import os, uuid, cv2
from ultralytics import YOLO

from main import _mjpeg_frames, _webcam_mjpeg, webcam_stream, get_usb_camera_index, get_usb_camera
camera_index = get_usb_camera_index()
# camera = get_usb_camera(camera_index)

from main import STATE, STATIC_DIR, BASE_DIR, get_usb_camera_index
BASE_DIR = BASE_DIR
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = STATIC_DIR

# 얼굴용 YOLO 모델 로드 (처음 한번만)
yolo_face = YOLO("yolov8n-face.pt") 
SAVE_DIR = "captures"
os.makedirs(SAVE_DIR, exist_ok=True)

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/config", StaticFiles(directory=str(BASE_DIR / "config")), name="config")
# Open your USB webcam
camera = get_usb_camera()
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "face-detectionV1.html")

@app.get("/webcam_index")
def get_webcam_index():
    camera_index = get_usb_camera_index()
    return {"camera_index": camera_index}

@app.get("/api/webcam/stream")
async def api_webcam_stream(webcam: int = 0):
    """[UPLINK] USB Webcam -> MJPEG stream for browser <img>"""
    if not camera.isOpened():
        return JSONResponse({"error": "Webcam not available"}, status_code=404)
    return StreamingResponse(_webcam_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/webcam/capture")
async def capture_and_resize(file: UploadFile = File(...)):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.jpg"
    path = os.path.join(SAVE_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    results = yolo_face(path, conf=0.5, verbose=False)
    if len(results[0].boxes) == 0:
        return {"saved_path": path, "box": None, "msg": "no face"}
    # 이미지 크기
    with Image.open(path) as im:
        W, H = im.size
    # 가장 큰 얼굴 선택
    x1,y1,x2,y2 = map(int, results[0].boxes[0].xyxy[0]) # 얼굴 1개일때, 여러개면 max로
    # spec 대로 확대
    x1_e = max(0, x1 - 40)
    y1_e = max(0, y1 - 40)
    x2_e = min(W, x2 + 40)
    y2_e = min(H, y2 + 40)
    box_size = {"x1": x1_e, "y1": y1_e, "x2": x2_e, "y2": y2_e}
    # ★ 핵심: crop해서 원본 경로에 덮어쓰기
    with Image.open(path) as im:
        cropped = im.crop((x1_e, y1_e, x2_e, y2_e))
        # 필요하면 고정 사이즈로 resize: cropped = cropped.resize((320, 320))
        cropped.save(path, "JPEG", quality=95)
    return {"saved_path": path, "box": box_size, "conf": float(results[0].boxes[0].conf[0])}

@app.post("/api/webcam/capture/{name}")
async def capture_and_resize(name: str, file: UploadFile = File(...)):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.jpg"
    path = os.path.join(SAVE_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    results = yolo_face(path, conf=0.5, verbose=False)
    if len(results[0].boxes) == 0:
        return {"saved_path": path, "box": None, "msg": "no face"}
    # 이미지 크기
    with Image.open(path) as im:
        W, H = im.size
    # 가장 큰 얼굴 선택
    x1,y1,x2,y2 = map(int, results[0].boxes[0].xyxy[0]) # 얼굴 1개일때, 여러개면 max로
    # spec 대로 확대
    x1_e = max(0, x1 - 40)
    y1_e = max(0, y1 - 40)
    x2_e = min(W, x2 + 40)
    y2_e = min(H, y2 + 40)
    box_size = {"x1": x1_e, "y1": y1_e, "x2": x2_e, "y2": y2_e}
    # ★ 핵심: crop해서 원본 경로에 덮어쓰기
    with Image.open(path) as im:
        cropped = im.crop((x1_e, y1_e, x2_e, y2_e))
        # 필요하면 고정 사이즈로 resize: cropped = cropped.resize((320, 320))
        cropped.save(path, "JPEG", quality=95)
    return {"saved_path": path, "box": box_size, "conf": float(results[0].boxes[0].conf[0])}

@app.post("/api/webcam/recognize")
async def recognize(file: UploadFile = File(...)):
    # 1. JPG 저장
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.jpg"
    # filename = f"{uuid.uuid4().hex[:6]}.jpg"
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("face-detection-serverV1:app", host="127.0.0.1", port=8000, reload=True)
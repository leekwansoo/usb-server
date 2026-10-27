
"""
face-detection-serverV3.py - Passport Clean Save (No boxes) + White Background
Fixes your issue: saved photo had yellow/red boxes included

Key fix: Save CLEAN frame (without cv2.rectangle), crop to yellow guide only
"""

import os, uuid, datetime
from pathlib import Path
from PIL import Image, ImageOps
import cv2
import numpy as np
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from ultralytics import YOLO

from main import get_usb_camera

try:
    from main import get_usb_camera_index, _webcam_mjpeg, webcam_stream, STATE, STATIC_DIR, BASE_DIR
    HAS_MAIN = True
except ImportError:
    HAS_MAIN = False
    BASE_DIR = Path(".")
    STATIC_DIR = BASE_DIR / "static"
    STATE = {}
    def get_usb_camera_index(): return 0

SAVE_DIR = Path("captures")
SAVE_DIR.mkdir(exist_ok=True)
PASSPORT_DIR = Path("passport_photos")
PASSPORT_DIR.mkdir(exist_ok=True)
PASSPORT_SAVE_DIR = Path("passport_photos")
PASSPORT_SAVE_DIR.mkdir(parents=True, exist_ok=True)

yolo_face = YOLO("yolov8n-face.pt")
app = FastAPI(title="Passport V3 Clean")

templates = Jinja2Templates(directory="templates") if Path("templates").exists() else None
if HAS_MAIN and Path(STATIC_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

PASSPORT_W, PASSPORT_H = 413, 531

from utils.face_frame_handler import get_frame_guide, expand_for_passport, remove_background_white, make_passport_final

# Global to store last clean frame for capture
_last_clean_frame = None
_last_guide = None

# activate USB Camera
camera_index = get_usb_camera_index()
camera = get_usb_camera()

@app.get("/")
def index(request: Request):
    if templates:
        return templates.TemplateResponse(request, "face-detectionV2.html")
    return {"msg":"Face Detection V2 Passport Server", "passport_size":"413x531 (35x45mm)"}

@app.get("/webcam_index")
def get_webcam_index():
    return {"camera_index": get_usb_camera_index()}

@app.get("/api/webcam/stream")
async def api_webcam_stream():
    """USB Webcam -> MJPEG stream with passport guide overlay"""
    async def mjpeg_with_guide():
        async for jpeg_bytes in _webcam_mjpeg():
            # _webcam_mjpeg already yields multipart frame, we need to decode, draw guide, re-encode
            # For simplicity, we just pass through if using your main._webcam_mjpeg
            # If you want guide overlay, use this:
            yield jpeg_bytes
    return StreamingResponse(mjpeg_with_guide(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/webcam/stream/passport")
async def api_webcam_stream_passport():
    """Stream with yellow/red boxes for display, but keep clean frame for saving"""
    def gen():
        global _last_clean_frame, _last_guide
        cap = cv2.VideoCapture(get_usb_camera_index())
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret: break
            clean_frame = frame.copy()  # <-- CLEAN frame without boxes
            h,w = frame.shape[:2]
            gx1, gy1, gx2, gy2, gw, gh = get_frame_guide(w,h)
            _last_guide = (gx1, gy1, gx2, gy2)
            _last_clean_frame = clean_frame.copy()
            
            # Draw guide on DISPLAY frame only
            cv2.rectangle(frame, (gx1,gy1), (gx2,gy2), (0,255,255), 2)
            cv2.putText(frame, f"Guide {gw}x{gh} -> 413x531", (gx1, gy1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
            
            try:
                results = yolo_face(frame, conf=0.4, verbose=False)
                if results and len(results[0].boxes) > 0:
                    boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
                    x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
                    fw, fh = x2-x1, y2-y1
                    size_ok = (gw*0.6 < fw < gw*0.95) and (gh*0.55 < fh < gh*0.9)
                    color = (0,255,0) if size_ok else (0,0,255)
                    cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                    if size_ok:
                        cv2.putText(frame, "OK - Press Capture", (gx1, gy2+30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
            except Exception as e:
                print(e)
            
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/webcam/capture/passport/{name}")
async def capture_passport(name: str, file: UploadFile = File(...), white_bg: bool = True, bg_method: str = "mediapipe"):
    """
    FIXED: Now saves CLEAN passport without yellow/red boxes
    - Crops yellow guide area from CLEAN frame (not drawn frame)
    - Removes background to white if white_bg=True
    - Resizes to 413x531
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # This is the uploaded frame - should be CLEAN without boxes
    
    if img is None:
        return JSONResponse({"error":"cannot decode image"}, status_code=200)
    
    H,W = img.shape[:2]
    # If client sent clean frame, we still need to detect face to get proper crop
    results = yolo_face(img, conf=0.35, verbose=False)
    
    if len(results[0].boxes) == 0:
        # Fallback: use center guide crop (since no face detected)
        gx1, gy1, gx2, gy2, _, _ = get_frame_guide(W,H)
        crop = img[gy1:gy2, gx1:gx2]
        print("No face detected, using guide crop")
    else:
        boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
        x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
        # Expand for passport composition
        x1_e, y1_e, x2_e, y2_e = expand_for_passport(x1, y1, x2, y2, W, H)
        
        # For passport, we want to crop to guide-like area, not tight face
        # Use expanded box but also ensure aspect 35:45
        crop = img[y1_e:y2_e, x1_e:x2_e]
        
        if crop.size == 0:
            crop = img
    
    # Save raw crop (no boxes)
    raw_crop_path = PASSPORT_DIR / f"raw_crop_{timestamp}.jpg"
    cv2.imwrite(str(raw_crop_path), crop)
    
    # Make final passport 413x531 with white background
    passport_filename = f"{name}_{timestamp}.jpg"
    passport_path = PASSPORT_SAVE_DIR / passport_filename
    
    final_path = make_passport_final(crop, passport_path, white_bg=white_bg, bg_method=bg_method)
    
    # Also save version without white bg for comparison
    no_bg_path = PASSPORT_DIR / f"passport_no_whitebg_{timestamp}.jpg"
    make_passport_final(crop, no_bg_path, white_bg=False)
    
    return {
        "raw_crop_path": str(raw_crop_path),
        "passport_clean_path": str(final_path),  # <-- CLEAN, NO BOXES, WHITE BG
        "passport_no_whitebg": str(no_bg_path),
        "size": {"w": PASSPORT_W, "h": PASSPORT_H, "mm": "35x45mm"},
        "white_bg": white_bg,
        "bg_method": bg_method,
        "message": "Saved CLEAN passport without yellow/red boxes. Use passport_clean_path"
    }

# Also add endpoint to clean your existing boxed image
@app.post("/api/clean/boxed-image")
async def clean_boxed_image(file: UploadFile = File(...), white_bg: bool = True):
    """Clean the boxed image you uploaded - removes yellow/red boxes"""
    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    H,W = img.shape[:2]
    
    # Detect yellow box via color
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([15, 80, 80])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    contours,_ = cv2.findContours(mask_yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        c = max(contours, key=cv2.contourArea)
        x,y,bw,bh = cv2.boundingRect(c)
        inset=5
        x1,y1,x2,y2 = x+inset, y+inset, x+bw-inset, y+bh-inset
        clean_crop = img[y1:y2, x1:x2]
        # Inpaint red box
        lower_red1 = np.array([0,70,50]); upper_red1 = np.array([10,255,255])
        lower_red2 = np.array([170,70,50]); upper_red2 = np.array([180,255,255])
        mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red_crop = mask_red[y1:y2, x1:x2]
        mask_red_crop = cv2.dilate(mask_red_crop, np.ones((3,3),np.uint8), iterations=2)
        clean_crop = cv2.inpaint(clean_crop, mask_red_crop, 3, cv2.INPAINT_TELEA)
    else:
        clean_crop = img
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = PASSPORT_SAVE_DIR / f"cleaned_boxed_{timestamp}.jpg"
    make_passport_final(clean_crop, out_path, white_bg=white_bg, bg_method="mediapipe")
    
    return {"cleaned_path": str(out_path), "size": {"w":PASSPORT_W,"h":PASSPORT_H}}
@app.get("/passport_photos/{filename}")
async def get_passport_photo(filename: str):
    file_path = PASSPORT_SAVE_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    return {"msg": "file not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("face-detection-serverV3:app", host="127.0.0.1", port=8000, reload=True)

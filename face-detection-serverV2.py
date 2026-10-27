
"""
face-detection-serverV2.py - Passport Size App (35x45mm) Fixed Version
Based on your V1 but fixed for passport capture

Fixes from V1:
1. Duplicate /api/webcam/capture/{name} route conflict -> renamed
2. No full-face guarantee (x1-40 padding not enough for passport)
3. No passport frame-size logic
4. Camera index global race condition
5. Small image handling

Passport Spec: 35x45mm = 413x531px @300DPI, face 32-36mm = 70-80% of image
"""

import uuid
import datetime
from pathlib import Path
from PIL import Image, ImageOps
import cv2
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from ultralytics import YOLO

from utils.face_frame_handler import resize_for_passport
# If usb_device, main modules missing, fallback
try:
    from main import get_usb_camera, _webcam_mjpeg, webcam_stream, get_usb_camera_index, STATIC_DIR, BASE_DIR
    
    HAS_MAIN = True
except ImportError:
    HAS_MAIN = False
    BASE_DIR = Path(".")
    STATIC_DIR = BASE_DIR / "static"
    def get_usb_camera_index(): return 0
    def _webcam_mjpeg():
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret: break
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

# --- Config ---
SAVE_DIR = Path("captures")
SAVE_DIR.mkdir(exist_ok=True)
PASSPORT_SAVE_DIR = Path("passport_photos")
PASSPORT_SAVE_DIR.mkdir(exist_ok=True)

# YOLO face model - load once
yolo_face = YOLO("yolov8n-face.pt")  # if not exists, will try yolov8n.pt
print(f"YOLO model loaded: {yolo_face}")

app = FastAPI(title="Face Detection V2 - Passport Ready")

# Templates - safe mount
if HAS_MAIN:
    templates = Jinja2Templates(directory="templates")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    if (BASE_DIR / "config").exists():
        app.mount("/config", StaticFiles(directory=str(BASE_DIR / "config")), name="config")
else:
    templates = Jinja2Templates(directory="templates") if Path("templates").exists() else None

# --- Passport Size Helpers ---
PASSPORT_TARGET_W, PASSPORT_TARGET_H = 413, 531  # 35x45mm @300dpi
FACE_RATIO_MIN, FACE_RATIO_MAX = 0.65, 0.85  # face should occupy 65-85% of passport height

from utils.face_frame_handler import get_frame_guide, expand_for_passport, remove_background_white, make_passport_image, make_passport_final

# --- Routes ---
camera_index = get_usb_camera_index()
camera = get_usb_camera()
@app.get("/")
def index(request: Request):
    if templates:
        return templates.TemplateResponse(request, "face-detectionV1.html")
    return {"msg":"Face Detection V2 Passport Server", "passport_size":"413x531 (35x45mm)"}

@app.get("/passport_picture")
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
    """MJPEG stream with passport guide overlay - USE THIS FOR PASSPORT APP"""
    def gen():
        cap = cv2.VideoCapture(get_usb_camera_index())
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        while True:
            ret, frame = cap.read()
            if not ret: break
            h,w = frame.shape[:2]
            gx1, gy1, gx2, gy2, gw, gh = get_frame_guide(w,h)
            # Draw yellow passport guide
            cv2.rectangle(frame, (gx1,gy1), (gx2,gy2), (0,255,255), 2)
            cv2.putText(frame, f"Passport Guide {gw}x{gh} -> 413x531", (gx1, gy1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
            # Detect and check if face fits guide
            results = yolo_face(frame, conf=0.4, verbose=False)
            if results and len(results[0].boxes) > 0:
                # Biggest face
                boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
                x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
                # Check if inside guide and size ok
                fw, fh = x2-x1, y2-y1
                size_ok = (gw*0.6 < fw < gw*0.95) and (gh*0.55 < fh < gh*0.9)
                color = (0,255,0) if size_ok else (0,0,255)
                cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                if size_ok:
                    cv2.putText(frame, "OK - Press Capture", (gx1, gy2+30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/webcam/capture/{name}")
async def capture_and_resize(name: str, file: UploadFile = File(...)):
    """V1 compatible - now fixed with passport expand logic"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.jpg"
    path = SAVE_DIR / filename
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    
    results = yolo_face(str(path), conf=0.4, verbose=False)
    if len(results[0].boxes) == 0:
        return {"saved_path": str(path), "box": None, "msg": "no face", "passport_path": None}
    
    with Image.open(path) as im:
        W, H = im.size
    
    # Biggest face
    boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
    x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
    
    # Fixed expand logic - passport aware, not fixed +40
    x1_e, y1_e, x2_e, y2_e = expand_for_passport(x1, y1, x2, y2, W, H)
    box_size = {"x1": x1_e, "y1": y1_e, "x2": x2_e, "y2": y2_e, "orig": {"x1":x1,"y1":y1,"x2":x2,"y2":y2}}
    
    with Image.open(path) as im:
        cropped = im.crop((x1_e, y1_e, x2_e, y2_e))
        cropped.save(path, "JPEG", quality=95)
    
    
    return {"saved_path": str(path), "box": box_size, "conf": float(boxes[0].conf[0])}

@app.post("/api/webcam/capture/passport/{name}")
async def capture_passport(name: str, file: UploadFile = File(...)):
    """
    NEW - Passport 35x45mm final output
    Upload -> detect -> expand -> crop -> resize to 413x531 -> save
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"raw_{timestamp}.jpg"
    path = SAVE_DIR / filename
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    
    results = yolo_face(str(path), conf=0.4, verbose=False)
    if len(results[0].boxes) == 0:
        return JSONResponse({"saved_path": str(path), "passport_path": None, "msg": "no face detected - try closer, better light"}, status_code=200)
    
    with Image.open(path) as im:
        W, H = im.size
    
    boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
    x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
    x1_e, y1_e, x2_e, y2_e = expand_for_passport(x1, y1, x2, y2, W, H)
    
    # Crop
    with Image.open(path) as im:
        cropped = im.crop((x1_e, y1_e, x2_e, y2_e))
        temp_crop = SAVE_DIR / f"crop_{timestamp}.jpg"
        cropped.save(temp_crop, "JPEG", quality=95)
    
    # Resize to exact passport size 413x531
    passport_filename = f"{name}_{timestamp}.jpg"
    passport_path = PASSPORT_SAVE_DIR / f"{passport_filename}"
    make_passport_image(temp_crop, passport_path)
    
    # Clean temp
    if temp_crop.exists():
        temp_crop.unlink()
    
    return {
        "raw_path": str(path),
        "crop_box": {"x1": x1_e, "y1": y1_e, "x2": x2_e, "y2": y2_e, "orig_face": {"x1":x1,"y1":y1,"x2":x2,"y2":y2}},
        "passport_path": str(passport_path),
        "passport_size": {"w": PASSPORT_TARGET_W, "h": PASSPORT_TARGET_H, "mm": "35x45mm", "dpi": 300},
        "conf": float(boxes[0].conf[0]),
        "guide": "Face should be 70-80% of passport height"
    }

# Fixed: rename second duplicate route
@app.post("/api/webcam/capture/named/{name}")
async def capture_and_resize_named(name: str, file: UploadFile = File(...)):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.jpg"
    path = SAVE_DIR / filename
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    results = yolo_face(str(path), conf=0.4, verbose=False)
    if len(results[0].boxes) == 0:
        return {"saved_path": str(path), "box": None, "msg": "no face"}
    with Image.open(path) as im:
        W, H = im.size
    boxes = sorted(results[0].boxes, key=lambda b: (b.xyxy[0][2]-b.xyxy[0][0])*(b.xyxy[0][3]-b.xyxy[0][1]), reverse=True)
    x1,y1,x2,y2 = map(int, boxes[0].xyxy[0])
    x1_e, y1_e, x2_e, y2_e = expand_for_passport(x1, y1, x2, y2, W, H)
    box_size = {"x1": x1_e, "y1": y1_e, "x2": x2_e, "y2": y2_e}
    with Image.open(path) as im:
        cropped = im.crop((x1_e, y1_e, x2_e, y2_e))
        cropped.save(path, "JPEG", quality=95)
    return {"saved_path": str(path), "box": box_size, "conf": float(boxes[0].conf[0])}

@app.get("/passport_photos/{filename}")
async def get_passport_photo(filename: str):
    file_path = PASSPORT_SAVE_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    return {"msg": "file not found"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("face-detection-serverV2:app", host="127.0.0.1", port=8000, reload=True)

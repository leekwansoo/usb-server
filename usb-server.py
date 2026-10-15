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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
    "Light1": {"state": "OFF", "power_w": 0},
    "Light2": {"state": "OFF", "power_w": 0},
    "Switch1": {"state": "OFF", "power_w": 0, "today_kwh": 0.45},
    "Switch2": {"state": "OFF", "power_w": 0, "today_kwh": 0.32},
    "Temp1": {"temperature": 23.5, "humidity": 58},
    "Camera1": {"online": True, "motion": False},
    "Camera2": {"online": True, "motion": False},
    "Webcam1": {"online": True, "motion": False},
    "Webcam2": {"online": True, "motion": False},
}

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

async def webcam_stream(websocket: WebSocket):
    await websocket.accept()
    while True:
        success, frame = camera.read()
        if not success:
            await asyncio.sleep(0.05)
            continue

        # Encode frame as JPEG
        ret, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        # Convert to Base64 for WebSocket transfer
        frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")

        # Send to client
        await websocket.send_text(frame_b64)

        # Small delay to avoid overloading CPU
        await asyncio.sleep(0.03)

async def _webcam_mjpeg():
    while True:
        success, frame = await asyncio.to_thread(camera.read)
        if not success:
            await asyncio.sleep(0.05)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        await asyncio.sleep(0.03)

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

@app.get("/api/status")
async def api_all_status():
    """[UPLINK] Terminal -> Server : Get all devices status (Both-way demo)"""
    # Simulate temp drift
    STATE["Temp1"]["temperature"] = round(22.5 + random.random()*3.5, 1)
    STATE["Temp1"]["humidity"] = random.randint(52, 68)
    
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "direction": "Terminal -> Server (UPLINK)",
        "devices": {
            "Temp1": {
                "temperature_c": STATE["Temp1"]["temperature"],
                "humidity": STATE["Temp1"]["humidity"],
                "battery": 87
            },
            "Door1": {"status": STATE["Door1"]},
            "Door2": {"status": STATE["Door2"]},
            "Light1": STATE["Light1"],
            "Light2": STATE["Light2"],
            "Switch1": {
                **STATE["Switch1"],
                "current_power_w": random.randint(800,1500) if STATE["Switch1"]["state"]=="ON" else 0
            },
            "Switch2": {
                **STATE["Switch2"],
                "current_power_w": random.randint(300,800) if STATE["Switch2"]["state"]=="ON" else 0
            },
            "Camera1": {"online": True, "motion": random.choice([True, False]), "recording": True},
            "Camera2": {"online": True, "motion": random.choice([True, False]), "recording": True},
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
                "Temp1": {"temperature": round(22.5 + random.random()*3.5, 1)},
                "Camera1": {"motion": random.choice([True, False])},
                "Camera2": {"motion": random.choice([True, False])},
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
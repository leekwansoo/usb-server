# Simple Test Server program for USB Camera Server


from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from usb_device import list_usb_devices
from main import get_usb_camera, nvr_handler
import cv2

from main import _mjpeg_frames, _webcam_mjpeg, play_video, webcam_stream, get_usb_camera_index, get_usb_camera
camera = get_usb_camera()

from main import STATE, STATIC_DIR, BASE_DIR, get_usb_camera_index
BASE_DIR = BASE_DIR
STATIC_DIR = STATIC_DIR

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Open your USB webcam
camera_index = get_usb_camera_index()
camera = cv2.VideoCapture(camera_index)

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "test.html")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("test-server:app", host="127.0.0.1", port=8000, reload=True)
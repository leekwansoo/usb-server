import cv2
import base64
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from usb_device import list_usb_devices

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
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
            await asyncio.sleep(0.01)
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

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.websocket("/ws/video")
async def video_ws(websocket: WebSocket):
    await webcam_stream(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
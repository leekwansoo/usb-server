# Testing the webcam_play function from main.py
import cv2
import asyncio
import base64
import uvicorn
from fastapi import FastAPI
from fastapi import WebSocket
from pathlib import Path
from usb_device import list_usb_devices

app = FastAPI()
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


@app.websocket("/ws/video")
async def video_ws(websocket: WebSocket):
    await webcam_stream(websocket)
      


if __name__ == "__main__":
    uvicorn.run("test:app", host="127.0.0.1", port=8004, reload=True)  # Run the FastAPI app for WebSocket streaming
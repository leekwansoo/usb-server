import cv2
import base64
import asyncio

from usb_device import list_usb_devices
from fastapi import WebSocket


camera = cv2.VideoCapture(0)

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

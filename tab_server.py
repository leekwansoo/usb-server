from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import cv2
import numpy as np
import base64

app = FastAPI()

# 마지막 프레임 저장 (다른 PC에서 스트리밍으로 보기 위해)
last_frame = None

@app.get("/", response_class=HTMLResponse)
async def get_camera_page():
    # 휴대폰에서 이 페이지에 접속하면 카메라가 켜집니다
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <h3>휴대폰 카메라 전송 중...</h3>
        <video id="video" autoplay playsinline style="width:100%"></video>
        <script>
            const video = document.getElementById('video');
            const ws = new WebSocket(`ws://${location.host}/ws`);

            ws.onopen = async () => {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "environment" }, audio: false 
                });
                video.srcObject = stream;
                
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');

                setInterval(() => {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0);
                    // jpeg로 압축해서 전송 (품질 0.6)
                    const data = canvas.toDataURL('image/jpeg', 0.6);
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(data);
                    }
                }, 100); // 100ms = 10fps, 50으로 하면 20fps
            };
        </script>
    </body>
    </html>
    """

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    global last_frame
    await websocket.accept()
    print("휴대폰 연결됨")
    try:
        while True:
            data = await websocket.receive_text()
            # data:image/jpeg;base64,.... 형태
            header, encoded = data.split(",", 1)
            img_data = base64.b64decode(encoded)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            last_frame = frame
            
            # 여기서 AI 모델 처리 가능
            # cv2.imshow("Phone Cam", frame)
            # cv2.waitKey(1)

    except Exception as e:
        print(f"연결 끊김: {e}")

@app.get("/video_feed")
async def video_feed():
    # 서버에서 카메라 화면을 MJPEG로 다른 브라우저에서 보는 용도
    from fastapi.responses import StreamingResponse
    def gen():
        import time
        while True:
            if last_frame is not None:
                _, jpeg = cv2.imencode('.jpg', last_frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.05)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tab_server:app", host="127.0.0.1", port=8000, reload=True)
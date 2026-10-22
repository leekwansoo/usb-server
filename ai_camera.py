from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
import cv2, base64, os, numpy as np
from ultralytics import YOLO
from deepface import DeepFace
import time

app = FastAPI()
yolo_model = YOLO("yolov8n-face.pt") # 얼굴 탐지 전용

# 등록된 얼굴 임베딩 DB
known_db = {} # { "Kwansoo_Lee": [embedding1, embedding2] }

def load_known_faces():
    print("등록된 얼굴 로딩 중...")
    for person_name in os.listdir("known_faces"):
        person_dir = os.path.join("known_faces", person_name)
        if not os.path.isdir(person_dir): continue
        embeddings = []
        for img_file in os.listdir(person_dir):
            path = os.path.join(person_dir, img_file)
            try:
                # DeepFace로 얼굴 임베딩 추출
                emb = DeepFace.represent(img_path=path, model_name="Facenet", enforce_detection=False)[0]["embedding"]
                embeddings.append(emb)
            except Exception as e:
                print(f"{path} 실패: {e}")
        if embeddings:
            known_db[person_name] = embeddings
    print(f"로딩 완료: {list(known_db.keys())}")

load_known_faces()
last_frame_result = None

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html><body>
    <h3>YOLO 안면인식 - 휴대폰 카메라 전송중</h3>
    <video id="v" autoplay playsinline style="width:100%"></video>
    <script>
        const v=document.getElementById('v');
        const ws=new WebSocket(`ws://${location.host}/ws`);
        ws.onopen=async()=>{
            const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user", width:640, height:480}});
            v.srcObject=stream;
            const c=document.createElement('canvas'); const ctx=c.getContext('2d');
            setInterval(()=>{
                c.width=v.videoWidth; c.height=v.videoHeight;
                ctx.drawImage(v,0,0);
                const d=c.toDataURL('image/jpeg',0.5);
                if(ws.readyState===1) ws.send(d);
            }, 100);
        };
    </script></body></html>
    """

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global last_frame_result
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            _, encoded = data.split(",",1)
            img_data = base64.b64decode(encoded)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # 1. YOLO로 얼굴 탐지
            results = yolo_model(frame, verbose=False, conf=0.5)
            for box in results[0].boxes:
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                face_crop = frame[y1:y2, x1:x2]
                if face_crop.size == 0: continue

                # 2. 얼굴 인식
                name = "Unknown"
                try:
                    curr_emb = DeepFace.represent(img_path=face_crop, model_name="Facenet", enforce_detection=False)[0]["embedding"]
                    # DB와 비교
                    min_dist = 999
                    for person, emb_list in known_db.items():
                        for db_emb in emb_list:
                            dist = np.linalg.norm(np.array(db_emb) - np.array(curr_emb))
                            if dist < min_dist and dist < 0.35: # 임계값, 낮을수록 엄격
                                min_dist = dist
                                name = person
                except:
                    pass

                color = (0,255,0) if name!="Unknown" else (0,0,255)
                cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                cv2.putText(frame, name, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            last_frame_result = frame
    except Exception as e:
        print("연결 종료", e)

@app.get("/video_feed")
def video_feed():
    def gen():
        while True:
            if last_frame_result is not None:
                _, jpeg = cv2.imencode('.jpg', last_frame_result)
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n'
            time.sleep(0.05)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ai_camera:app", host="127.0.0.1", port=8000, reload=True)
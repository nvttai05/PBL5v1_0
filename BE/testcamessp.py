import cv2
import numpy as np
import time
from fastapi import FastAPI, WebSocket
from ultralytics import YOLO
import uvicorn

app = FastAPI()

# Load model YOLOv11n
model = YOLO("best.pt")

# FPS debug
frame_count = 0
start_time = time.time()

# Điều tiết detect
last_detect_time = 0
DETECT_INTERVAL = 0.2  # 200ms (~5 FPS detect)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global frame_count, start_time, last_detect_time

    await websocket.accept()
    print("🟢 ESP32 Connected")

    while True:
        try:
            # ===== Nhận ảnh =====
            data = await websocket.receive_bytes()

            # ===== Đếm FPS =====
            frame_count += 1
            if time.time() - start_time >= 1:
                print(f"📊 FPS nhận: {frame_count}")
                frame_count = 0
                start_time = time.time()

            # ===== Decode =====
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                continue

            # Resize cho nhanh
            frame = cv2.resize(frame, (320, 240))

            # ===== Detect có kiểm soát =====
            now = time.time()
            if now - last_detect_time > DETECT_INTERVAL:
                last_detect_time = now

                results = model(frame)
                frame = results[0].plot()

                # In object
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    name = model.names[cls_id]
                    print("👉", name)

            # ===== Hiển thị =====
            cv2.imshow("ESP32 YOLO Test", frame)
            cv2.waitKey(1)

        except Exception as e:
            print("❌ Error:", e)
            break


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
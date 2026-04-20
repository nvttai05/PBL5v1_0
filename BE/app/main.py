import asyncio
import base64
import time as time_module
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import create_tables
from app.core.websocket_manager import manager
from app.services.yolo_service import yolo_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting English Object Recognition API...")
    print(f"Server running on http://{settings.HOST}:{settings.PORT}")

    # Tạo database tables
    try:
        create_tables()
    except Exception as e:
        print(f"Warning: Could not create tables: {e}")

    # Seed dữ liệu
    try:
        from app.core.seed import seed_object_dictionary, seed_default_user
        from app.core.database import SessionLocal
        db = SessionLocal()
        seed_default_user(db)       # ← tạo user test trước
        seed_object_dictionary(db)  # ← sau đó seed objects
        db.close()
    except Exception as e:
        print(f"Seed data warning: {e}")

    # Load YOLO model
    try:
        if yolo_service.model is None:
            print("Loading YOLO model... (this may take a few seconds)")
        else:
            print("YOLO model already loaded")
    except Exception as e:
        print(f"Could not load YOLO model: {e}")

    yield
    print("Shutting down API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API cho hệ thống học tiếng Anh qua nhận diện đồ vật",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Import routers sau khi app được tạo
from app.routers import status, detect, speak, history, quiz, object, auth

app.include_router(status.router)
app.include_router(detect.router)
app.include_router(speak.router)
app.include_router(history.router)
app.include_router(quiz.router)
app.include_router(object.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {
        "message": "English Object Recognition Learning System API is running",
        "docs": "/docs",
        "status": "/api/v1/status"
    }


@app.websocket("/api/v1/ws/detect")
async def websocket_detect(websocket: WebSocket):
    await manager.connect_cam(websocket)
    last_processed_time = 0.0
    try:
        while True:
            data = await websocket.receive_bytes()
            now = time_module.time()
            if now - last_processed_time < 0.083:
                continue
            last_processed_time = now
            result = await asyncio.to_thread(yolo_service.detect_objects, data)
            detections = result.get("detections", [])
            base64_image = base64.b64encode(data).decode()
            await manager.broadcast_to_app({
                "type": "detection",
                "image": base64_image,
                "image_width": 320,
                "image_height": 240,
                "detections": detections,
                "timestamp": datetime.now().isoformat()
            })
    except WebSocketDisconnect:
        manager.disconnect_cam(websocket)
    except Exception as e:
        print(f"Cam Error: {e}")
        manager.disconnect_cam(websocket)


@app.websocket("/api/v1/ws/app")
async def websocket_app(websocket: WebSocket):
    await manager.connect_app(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket App error: {e}")
    finally:
        manager.disconnect_app(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
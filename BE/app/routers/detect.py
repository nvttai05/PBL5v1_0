import asyncio
import base64
import time
from contextlib import suppress

import httpx
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.websocket_manager import manager
from app.services.history_service import history_service
from app.services.tts_service import tts_service
from app.services.yolo_service import yolo_service

router = APIRouter(prefix="/api/v1", tags=["Detection"])

# --- CẤU HÌNH ---
SPEAKER_URL = "http://192.168.2.106/play"
BASE_URL = "http://192.168.2.104:8000"

# FE đang vẽ theo ảnh 320x240
IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240

# --- COOLDOWN PHÁT ÂM ---
last_spoken_object = ""
last_spoken_time = 0.0
COOLDOWN_SAME_OBJ = 3.0
COOLDOWN_ANY_OBJ = 2.0

# HTTP client dùng lại connection
http_client = httpx.AsyncClient(timeout=1.0)


def _save_history_sync(first_obj: dict, processing_time_ms: float):
    db = SessionLocal()
    try:
        history_service.create_history(
            db=db,
            user_id=1,
            object_name_en=first_obj["class_name"],
            object_name_vn=first_obj.get("name_vn", first_obj["class_name"]),
            confidence=first_obj["confidence"],
            duration_seconds=processing_time_ms / 1000.0,
        )
    except Exception as e:
        print(f"⚠️ Save history error: {e}")
    finally:
        db.close()


async def handle_detection_side_effects(first_obj: dict, processing_time_ms: float):
    global last_spoken_object, last_spoken_time

    label = first_obj["class_name"]
    now = time.monotonic()
    time_passed = now - last_spoken_time

    if label == last_spoken_object:
        if time_passed < COOLDOWN_SAME_OBJ:
            return
    else:
        if time_passed < COOLDOWN_ANY_OBJ:
            return

    last_spoken_object = label
    last_spoken_time = now

    try:
        if tts_service.audio_exists(label):
            audio_url = tts_service.get_audio_url(label)
            full_url = BASE_URL + audio_url

            try:
                await http_client.post(
                    SPEAKER_URL,
                    json={"audio_url": full_url},
                )
                print(f"🔊 Playing: {label} -> {audio_url}")
            except Exception as e:
                print(f"⚠️ Speaker error: {e}")
        else:
            print(f"⚠️ Missing pregenerated audio for: {label}")
    except Exception as e:
        print(f"⚠️ Audio handling error: {e}")

    asyncio.create_task(
        asyncio.to_thread(_save_history_sync, first_obj, processing_time_ms)
    )


async def push_latest_frame(frame_queue: asyncio.Queue, frame_bytes: bytes):
    if frame_queue.full():
        try:
            frame_queue.get_nowait()
            frame_queue.task_done()
        except asyncio.QueueEmpty:
            pass
    frame_queue.put_nowait(frame_bytes)


async def detector_worker(frame_queue: asyncio.Queue):
    processed_count = 0
    processed_fps_start = time.perf_counter()

    while True:
        frame_bytes = await frame_queue.get()
        try:
            result = await asyncio.to_thread(yolo_service.detect_objects, frame_bytes)
            detections = result.get("detections", [])
            processing_time_ms = result.get("processing_time_ms", 0.0)

            base64_image = base64.b64encode(frame_bytes).decode("ascii")

            await manager.broadcast_to_app({
                "type": "detection",
                "image": base64_image,
                "image_width": IMAGE_WIDTH,
                "image_height": IMAGE_HEIGHT,
                "detections": detections,
                "processing_time_ms": processing_time_ms,
                "timestamp": time.time()
            })

            if detections:
                first_obj = detections[0]
                asyncio.create_task(
                    handle_detection_side_effects(first_obj, processing_time_ms)
                )

            processed_count += 1
            elapsed = time.perf_counter() - processed_fps_start
            if elapsed >= 1.0:
                print(f"🚀 Detect FPS: {processed_count} | YOLO: {processing_time_ms:.2f} ms")
                processed_count = 0
                processed_fps_start = time.perf_counter()

        except Exception as e:
            print(f"🚨 Detector worker error: {e}")
        finally:
            frame_queue.task_done()


@router.websocket("/ws/detect")
async def websocket_detect(websocket: WebSocket):
    await manager.connect_cam(websocket)
    print("🟢 ESP32-CAM connected")

    frame_queue = asyncio.Queue(maxsize=1)
    worker_task = asyncio.create_task(detector_worker(frame_queue))

    receive_count = 0
    receive_fps_start = time.perf_counter()

    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            await push_latest_frame(frame_queue, frame_bytes)

            receive_count += 1
            elapsed = time.perf_counter() - receive_fps_start
            if elapsed >= 1.0:
                print(f"📥 Receive FPS from ESP32: {receive_count}")
                receive_count = 0
                receive_fps_start = time.perf_counter()

    except WebSocketDisconnect:
        print("🔴 CAM disconnected")
    except Exception as e:
        print(f"🚨 WebSocket detect error: {e}")
    finally:
        manager.disconnect_cam(websocket)
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
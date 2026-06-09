import asyncio
import base64
import json
import time
from collections import defaultdict, deque
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

# ======================================================
# CONFIG
# ======================================================
SPEAKER_URL = "http://192.168.2.102/play"
BASE_URL = "http://192.168.2.101:8000"

IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240

# ======================================================
# STUDY SESSION STATE
# ======================================================
study_session_active = False

# ======================================================
# SPEAKER COOLDOWN
# ======================================================
last_spoken_object = ""
last_spoken_time = 0.0

# Loa đọc thưa hơn để tránh spam ESP32 loa
COOLDOWN_SAME_OBJ = 4.0
COOLDOWN_ANY_OBJ = 4.0

speaker_lock = asyncio.Lock()
speaker_busy_until = 0.0

# Cho ESP32 loa nghỉ thêm một chút sau mỗi lần gọi
SPEAKER_EXTRA_GAP = 0.8
SPEAKER_MIN_BUSY_SECONDS = 2.2
# ======================================================
# HISTORY SAVE CONDITION
# ======================================================
# Yêu cầu: cùng 1 object được nhận diện >= 10 lần/giây trong 2 giây
# Tức là trong 2 giây gần nhất phải có >= 20 detection cùng class.
STABLE_WINDOW_SECONDS = 2.0
REQUIRED_DETECTIONS_PER_SECOND = 5
REQUIRED_DETECTIONS_IN_WINDOW = int(
    STABLE_WINDOW_SECONDS * REQUIRED_DETECTIONS_PER_SECOND
)

# Tránh lưu history liên tục sau khi đã đạt điều kiện
# Vì history_service cũng merge trong 120s, để 120s là hợp lý.
HISTORY_SAVE_COOLDOWN_SECONDS = 120.0

# Lưu timestamp detect theo từng object
object_detection_windows = defaultdict(deque)

# Ghi nhớ lần lưu history gần nhất theo object
last_history_saved_at = {}

# HTTP client dùng lại connection
http_client = httpx.AsyncClient(timeout=2.0)


# ======================================================
# HISTORY HELPERS
# ======================================================
def _save_history_sync(first_obj: dict, duration_seconds: float):
    db = SessionLocal()
    try:
        history_service.create_history(
            db=db,
            user_id=1,
            object_name_en=first_obj["class_name"],
            object_name_vn=first_obj.get("name_vn", first_obj["class_name"]),
            confidence=first_obj["confidence"],
            duration_seconds=duration_seconds,
        )

        print(
            f"✅ Saved history: {first_obj['class_name']} | "
            f"duration={duration_seconds:.2f}s | "
            f"confidence={first_obj['confidence']:.3f}"
        )

    except Exception as e:
        print(f"⚠️ Save history error: {e}")
    finally:
        db.close()


def reset_stability_windows():
    object_detection_windows.clear()


def update_object_stability(first_obj: dict) -> dict:
    """
    Cập nhật cửa sổ detection 2 giây cho object vừa detect.

    Điều kiện lưu:
    - Cùng class_name xuất hiện >= 20 lần trong 2 giây gần nhất.
    """
    now = time.monotonic()

    label = first_obj["class_name"].strip().lower()
    window = object_detection_windows[label]

    window.append({
        "time": now,
        "confidence": float(first_obj.get("confidence", 0.0)),
        "object": first_obj,
    })

    cutoff = now - STABLE_WINDOW_SECONDS

    while window and window[0]["time"] < cutoff:
        window.popleft()

    count = len(window)
    fps = count / STABLE_WINDOW_SECONDS

    avg_confidence = 0.0
    if count > 0:
        avg_confidence = sum(item["confidence"] for item in window) / count

    stable = count >= REQUIRED_DETECTIONS_IN_WINDOW

    return {
        "label": label,
        "count": count,
        "fps": fps,
        "avg_confidence": avg_confidence,
        "stable": stable,
        "window_seconds": STABLE_WINDOW_SECONDS,
    }


def can_save_history_for_label(label: str) -> bool:
    """
    Sau khi object đã ổn định, chỉ lưu history mỗi label 1 lần trong 60s
    để tránh spam DB.
    """
    now = time.monotonic()
    last_saved = last_history_saved_at.get(label)

    if last_saved is None:
        return True

    return (now - last_saved) >= HISTORY_SAVE_COOLDOWN_SECONDS


def mark_history_saved(label: str):
    last_history_saved_at[label] = time.monotonic()


# ======================================================
# SPEAKER
# ======================================================
async def try_speak(first_obj: dict):
    """
    Logic loa đơn giản như code cũ:
    - Chỉ phát khi đang START.
    - Cooldown cùng vật / khác vật.
    - Gọi ESP32 speaker /play.
    - Không dùng speaker_busy_until.
    - Không dùng DURATION_MAP.
    """
    global last_spoken_object, last_spoken_time

    if not study_session_active:
        return

    label = first_obj["class_name"].strip().lower()
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
                print(f"⚠️ Speaker error: {type(e).__name__}: {repr(e)}")
        else:
            print(f"⚠️ Missing pregenerated audio for: {label}")

    except Exception as e:
        print(f"⚠️ Audio handling error: {type(e).__name__}: {repr(e)}")


async def handle_detection_side_effects(first_obj: dict):
    """
    Xử lý sau khi YOLO detect được object:
    - START thì mới xử lý.
    - Phát loa theo cooldown.
    - Lưu lịch sử chỉ khi cùng object đạt >= 10 detections/s trong 2s.
    """
    if not study_session_active:
        return

    # 1. Phát loa theo cooldown
    asyncio.create_task(try_speak(first_obj))

    # 2. Cập nhật độ ổn định của object
    stability = update_object_stability(first_obj)

    label = stability["label"]
    count = stability["count"]
    fps = stability["fps"]
    stable = stability["stable"]
    avg_conf = stability["avg_confidence"]

    print(
        f"📊 Stability {label}: "
        f"{count}/{REQUIRED_DETECTIONS_IN_WINDOW} detections "
        f"in {STABLE_WINDOW_SECONDS:.1f}s | "
        f"{fps:.2f} FPS | stable={stable}"
    )

    # 3. Nếu chưa đủ 10FPS cùng vật trong 2 giây thì không lưu
    if not stable:
        return

    # 4. Nếu đủ điều kiện nhưng vừa lưu gần đây rồi thì không lưu tiếp
    if not can_save_history_for_label(label):
        print(f"⏳ Skip history for {label}: saved recently")
        return

    # 5. Lưu history với duration = 2 giây ổn định
    stable_obj = dict(first_obj)
    stable_obj["confidence"] = avg_conf

    mark_history_saved(label)

    asyncio.create_task(
        asyncio.to_thread(
            _save_history_sync,
            stable_obj,
            STABLE_WINDOW_SECONDS,
        )
    )


# ======================================================
# FRAME QUEUE
# ======================================================
async def push_latest_frame(frame_queue: asyncio.Queue, frame_bytes: bytes):
    if frame_queue.full():
        try:
            frame_queue.get_nowait()
            frame_queue.task_done()
        except asyncio.QueueEmpty:
            pass

    frame_queue.put_nowait(frame_bytes)


# ======================================================
# DETECTOR WORKER
# ======================================================
async def detector_worker(frame_queue: asyncio.Queue):
    global study_session_active

    processed_count = 0
    processed_fps_start = time.perf_counter()

    while True:
        frame_bytes = await frame_queue.get()

        try:
            base64_image = base64.b64encode(frame_bytes).decode("ascii")

            # ==================================================
            # STOP MODE:
            # Chỉ gửi ảnh xuống FE, không YOLO, không bbox, không loa, không history.
            # ==================================================
            if not study_session_active:
                await manager.broadcast_to_app({
                    "type": "detection",
                    "mode": "preview",
                    "image": base64_image,
                    "image_width": IMAGE_WIDTH,
                    "image_height": IMAGE_HEIGHT,
                    "detections": [],
                    "processing_time_ms": 0.0,
                    "study_session_active": False,
                    "history_save_ready": False,
                    "stable_object": None,
                    "timestamp": time.time(),
                })
                continue

            # ==================================================
            # START MODE:
            # Chạy YOLO + gửi ảnh + bbox xuống FE.
            # ==================================================
            result = await asyncio.to_thread(
                yolo_service.detect_objects,
                frame_bytes,
            )

            detections = result.get("detections", [])
            processing_time_ms = result.get("processing_time_ms", 0.0)

            stable_info = None

            if detections:
                first_obj = detections[0]
                stable_info = update_object_stability(first_obj)

                label = first_obj["class_name"].strip().lower()

                # ==================================================
                # Chỉ khi cùng 1 object ổn định đủ 10 frame / 2 giây
                # thì mới phát loa và mới xét lưu lịch sử.
                # ==================================================
                if stable_info["stable"]:
                    # 1. Phát loa theo cooldown 3-4 giây
                    asyncio.create_task(try_speak(first_obj))

                    # 2. Lưu lịch sử nếu cùng từ chưa được lưu trong 2 phút gần đây
                    if can_save_history_for_label(label):
                        stable_obj = dict(first_obj)
                        stable_obj["confidence"] = stable_info["avg_confidence"]

                        mark_history_saved(label)

                        asyncio.create_task(
                            asyncio.to_thread(
                                _save_history_sync,
                                stable_obj,
                                STABLE_WINDOW_SECONDS,
                            )
                        )
                    else:
                        print(f"⏳ Skip history for {label}: saved recently")

            await manager.broadcast_to_app({
                "type": "detection",
                "mode": "study",
                "image": base64_image,
                "image_width": IMAGE_WIDTH,
                "image_height": IMAGE_HEIGHT,
                "detections": detections,
                "processing_time_ms": processing_time_ms,
                "study_session_active": True,
                "history_save_ready": bool(stable_info and stable_info["stable"]),
                "stable_object": stable_info,
                "timestamp": time.time(),
            })

            processed_count += 1
            elapsed = time.perf_counter() - processed_fps_start

            if elapsed >= 1.0:
                print(
                    f"🚀 Detect FPS: {processed_count} | "
                    f"YOLO: {processing_time_ms:.2f} ms"
                )
                processed_count = 0
                processed_fps_start = time.perf_counter()

        except Exception as e:
            print(f"🚨 Detector worker error: {e}")

        finally:
            frame_queue.task_done()


# ======================================================
# WEBSOCKET DETECT
# ======================================================
@router.websocket("/ws/detect")
async def websocket_detect(websocket: WebSocket):
    global study_session_active
    global last_spoken_object, last_spoken_time

    await manager.connect_cam(websocket)
    print("🟢 ESP32-S3 CAM connected")

    frame_queue = asyncio.Queue(maxsize=1)
    worker_task = asyncio.create_task(detector_worker(frame_queue))

    receive_count = 0
    receive_fps_start = time.perf_counter()

    try:
        while True:
            message = await websocket.receive()

            # ==================================================
            # TEXT MESSAGE: START/STOP từ nút ESP32-S3
            # ==================================================
            if message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except Exception as e:
                    print(f"⚠️ Invalid JSON from ESP32-S3: {e}")
                    continue

                if data.get("type") == "button":
                    new_state = bool(data.get("study_session_active", False))

                    # STOP -> START
                    if new_state and not study_session_active:
                        print("▶️ Study session START")
                        reset_stability_windows()
                        last_spoken_object = ""
                        last_spoken_time = 0.0


                    # START -> STOP
                    if not new_state and study_session_active:
                        print("⏹️ Study session STOP")
                        reset_stability_windows()
                        last_spoken_object = ""
                        last_spoken_time = 0.0

                    study_session_active = new_state

                    status_message = {
                        "type": "study_session_status",
                        "study_session_active": study_session_active,
                        "history_rule": {
                            "required_detections_per_second": REQUIRED_DETECTIONS_PER_SECOND,
                            "window_seconds": STABLE_WINDOW_SECONDS,
                            "required_detections_in_window": REQUIRED_DETECTIONS_IN_WINDOW,
                        },
                        "timestamp": time.time(),
                    }

                    print(f"🔘 Study session active: {study_session_active}")

                    await manager.broadcast_to_app(status_message)
                    await manager.broadcast_to_cam(status_message)

                continue

            # ==================================================
            # BINARY MESSAGE: ảnh JPEG từ ESP32-S3
            # ==================================================
            frame_bytes = message.get("bytes")

            if frame_bytes is None:
                continue

            await push_latest_frame(frame_queue, frame_bytes)

            receive_count += 1
            elapsed = time.perf_counter() - receive_fps_start

            if elapsed >= 1.0:
                print(f"📥 Receive FPS from ESP32-S3: {receive_count}")
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
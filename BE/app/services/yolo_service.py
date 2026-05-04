from os import name
import time
import io
from typing import Dict, Any

import torch
from PIL import Image
from ultralytics import YOLO

from app.core.config import settings


VN_MAP = {
    "person": "người",
    "bicycle": "xe đạp",
    "car": "xe hơi",
    "motorcycle": "xe máy",
    "bus": "xe buýt",
    "truck": "xe tải",
    "boat": "thuyền",
    "bench": "ghế dài",
    "bird": "chim",
    "cat": "mèo",
    "dog": "chó",
    "horse": "ngựa",
    "sheep": "cừu",
    "cow": "bò",
    "elephant": "voi",
    "bear": "gấu",
    "zebra": "ngựa vằn",
    "giraffe": "hươu cao cổ",
    "backpack": "ba lô",
    "umbrella": "ô",
    "handbag": "túi xách",
    "tie": "cà vạt",
    "suitcase": "vali",
    "bottle": "chai",
    "wine glass": "ly rượu",
    "cup": "cốc",
    "fork": "nĩa",
    "knife": "dao",
    "spoon": "muỗng",
    "bowl": "bát",
    "banana": "chuối",
    "apple": "táo",
    "sandwich": "bánh mì kẹp",
    "orange": "cam",
    "broccoli": "bông cải xanh",
    "carrot": "cà rốt",
    "hot dog": "xúc xích",
    "pizza": "pizza",
    "donut": "bánh donut",
    "cake": "bánh kem",
    "chair": "ghế",
    "couch": "ghế sofa",
    "potted plant": "cây cảnh",
    "bed": "giường",
    "dining table": "bàn ăn",
    "toilet": "bồn cầu",
    "tv": "ti vi",
    "laptop": "laptop",
    "mouse": "chuột máy tính",
    "remote": "remote",
    "keyboard": "bàn phím",
    "cell phone": "điện thoại",
    "microwave": "lò vi sóng",
    "oven": "lò nướng",
    "toaster": "máy nướng bánh mì",
    "sink": "bồn rửa",
    "refrigerator": "tủ lạnh",
    "book": "sách",
    "clock": "đồng hồ",
    "vase": "bình hoa",
    "scissors": "kéo",
    "teddy bear": "gấu bông",
    "hair drier": "máy sấy tóc",
    "toothbrush": "bàn chải đánh răng",
}


class YOLOService:
    def __init__(self):
        self.model = None
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD
        self.imgsz = settings.IMGSZ

        self.use_cuda = torch.cuda.is_available()
        self.device = 0 if self.use_cuda else "cpu"
        self.use_half = self.use_cuda  # FP16 chỉ bật khi có CUDA

        self._load_model()

    def _load_model(self):
        try:
            print("torch.cuda.is_available():", torch.cuda.is_available())

            if torch.cuda.is_available():
                print("GPU name:", torch.cuda.get_device_name(0))
                torch.backends.cudnn.benchmark = True

            print("Loading YOLO model...")
            self.model = YOLO(settings.YOLO_MODEL_PATH)

            # Warmup đúng kích thước đang dùng
            dummy = Image.new("RGB", (self.imgsz, self.imgsz))

            with torch.inference_mode():
                self.model.predict(
                    source=dummy,
                    imgsz=self.imgsz,
                    conf=self.confidence_threshold,
                    device=self.device,
                    half=self.use_half,
                    verbose=False,
                    max_det=5,
                )

            print(
                f"YOLO model loaded successfully! "
                f"(device={self.device}, half={self.use_half}, imgsz={self.imgsz}, conf={self.confidence_threshold})"
            )

            # Kiểm tra model đang ở device nào
            try:
                print("Model device:", self.model.device)
            except Exception:
                pass

        except Exception as e:
            print(f"YOLO model load failed! (Error: {e})")
            self.model = None
            raise

    def detect_objects(self, image_bytes: bytes) -> Dict[str, Any]:
        if not self.model:
            raise Exception("YOLO model not loaded!")

        start_time = time.perf_counter()

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            with torch.inference_mode():
                results = self.model.predict(
                    source=image,
                    imgsz=self.imgsz,
                    conf=self.confidence_threshold,
                    device=self.device,
                    half=self.use_half,
                    verbose=False,
                    max_det=5,
                )

            detections = []
            result = results[0]

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()

                class_name_en = result.names[class_id]
                name_vn = VN_MAP.get(class_name_en.lower(), class_name_en)

                detections.append({
                    "class_name": class_name_en,
                    "name_vn": name_vn,
                    "confidence": round(confidence, 3),
                    "bbox": [int(x) for x in bbox],
                })

            # confidence cao trước
            detections.sort(key=lambda x: x["confidence"], reverse=True)

            processing_time = (time.perf_counter() - start_time) * 1000

            return {
                "detections": detections,
                "processing_time_ms": round(processing_time, 2),
                "total_object": len(detections)
            }

        except Exception as e:
            raise Exception(f"YOLO detection failed! (Error: {e})")

yolo_service = YOLOService()
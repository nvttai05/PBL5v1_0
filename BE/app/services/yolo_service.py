from os import name
import time
import io
from typing import Dict, Any, List

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
        self.max_det = settings.YOLO_MAX_DET

        self.person_confidence_threshold = settings.PERSON_CONFIDENCE_THRESHOLD
        self.person_min_area_ratio = settings.PERSON_MIN_AREA_RATIO
        self.person_min_width_ratio = settings.PERSON_MIN_WIDTH_RATIO
        self.person_min_height_ratio = settings.PERSON_MIN_HEIGHT_RATIO
        self.ignore_person_when_other_objects_exist = settings.IGNORE_PERSON_WHEN_OTHER_OBJECTS_EXIST

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

            dummy = Image.new("RGB", (self.imgsz, self.imgsz))

            with torch.inference_mode():
                self.model.predict(
                    source=dummy,
                    imgsz=self.imgsz,
                    conf=self.confidence_threshold,
                    device=self.device,
                    half=self.use_half,
                    verbose=False,
                    max_det=self.max_det,
                )

            print(
                f"YOLO model loaded successfully! "
                f"(device={self.device}, half={self.use_half}, imgsz={self.imgsz})"
                f"conf={self.confidence_threshold}, person_conf={self.person_confidence_threshold})"
            )

            try:
                print("Model device:", self.model.device)
            except Exception:
                pass

        except Exception as e:
            print(f"YOLO model load failed! (Error: {e})")
            self.model = None
            raise

    def _calculate_box_ratios(
            self,
            bbox: List[float],
            frame_width: int,
            frame_height: int
    ) -> Dict[str, float]:
        x1, y1, x2, y2 = bbox

        box_width = max(0.0, x2 - x1)
        box_height = max(0.0, y2 - y1)

        frame_area = max(1.0, frame_width * frame_height)
        box_area = box_width * box_height

        return {
            "area_ratio": box_area / frame_area,
            "width_ratio": box_width / max(1.0, frame_width),
            "height_ratio": box_height / max(1.0, frame_height),
        }

    def _is_box_touching_edge(
            self,
            bbox: List[float],
            frame_width: int,
            frame_height: int,
            edge_ratio: float = 0.03
    ) -> bool:
        x1, y1, x2, y2 = bbox

        edge_x = frame_width * edge_ratio
        edge_y = frame_height * edge_ratio

        return (
                x1 <= edge_x or
                y1 <= edge_y or
                x2 >= frame_width - edge_x or
                y2 >= frame_height - edge_y
        )

    def _should_keep_person(
            self,
            confidence: float,
            bbox: List[float],
            frame_width: int,
            frame_height: int
    ) -> bool:

        if confidence < self.person_confidence_threshold:
            return False

        ratios = self._calculate_box_ratios(
            bbox=bbox,
            frame_width=frame_width,
            frame_height=frame_height
        )

        area_ratio = ratios["area_ratio"]
        width_ratio = ratios["width_ratio"]
        height_ratio = ratios["height_ratio"]

        if area_ratio < self.person_min_area_ratio:
            return False

        if width_ratio < self.person_min_width_ratio:
            return False

        if height_ratio < self.person_min_height_ratio:
            return False

        touching_edge = self._is_box_touching_edge(
            bbox=bbox,
            frame_width=frame_width,
            frame_height=frame_height
        )

        if touching_edge and area_ratio < 0.20:
            return False

        return True

    def _should_keep_detection(
            self,
            class_name_en: str,
            confidence: float,
            bbox: List[float],
            frame_width: int,
            frame_height: int
    ) -> bool:
        class_name = class_name_en.lower().strip()

        if class_name == "person":
            return self._should_keep_person(
                confidence=confidence,
                bbox=bbox,
                frame_width=frame_width,
                frame_height=frame_height
            )

        return confidence >= self.confidence_threshold

    def _remove_person_if_other_objects_exist(
            self,
            detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        non_person_detections = [
            item for item in detections
            if item["class_name"].lower() != "person"
        ]

        if non_person_detections:
            return non_person_detections

        return detections

    def detect_objects(self, image_bytes: bytes) -> Dict[str, Any]:
        if not self.model:
            raise Exception("YOLO model not loaded!")

        start_time = time.perf_counter()

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            frame_width, frame_height = image.size

            with torch.inference_mode():
                results = self.model.predict(
                    source=image,
                    imgsz=self.imgsz,
                    conf=self.confidence_threshold,
                    device=self.device,
                    half=self.use_half,
                    verbose=False,
                    max_det=self.max_det,
                )

            detections = []
            filtered_out = []

            result = results[0]

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                bbox_float = box.xyxy[0].tolist()

                class_name_en = result.names[class_id]
                class_name_lower = class_name_en.lower().strip()
                name_vn = VN_MAP.get(class_name_lower, class_name_en)

                keep = self._should_keep_detection(
                    class_name_en=class_name_en,
                    confidence=confidence,
                    bbox=bbox_float,
                    frame_width=frame_width,
                    frame_height=frame_height
                )

                ratios = self._calculate_box_ratios(
                    bbox=bbox_float,
                    frame_width=frame_width,
                    frame_height=frame_height
                )

                detection_item = {
                    "class_name": class_name_en,
                    "name_vn": name_vn,
                    "confidence": round(confidence, 3),
                    "bbox": [int(x) for x in bbox_float],
                    "area_ratio": round(ratios["area_ratio"], 3),
                    "width_ratio": round(ratios["width_ratio"], 3),
                    "height_ratio": round(ratios["height_ratio"], 3),
                }

                if keep:
                    detections.append(detection_item)
                else:
                    filtered_out.append({
                        **detection_item,
                        "reason": "filtered_by_person_rule"
                        if class_name_lower == "person"
                        else "filtered_by_confidence"
                    })

            detections.sort(key=lambda x: x["confidence"], reverse=True)

            if self.ignore_person_when_other_objects_exist:
                detections = self._remove_person_if_other_objects_exist(detections)

            processing_time = (time.perf_counter() - start_time) * 1000

            return {
                "detections": detections,
                "processing_time_ms": round(processing_time, 2),
                "total_object": len(detections)
                # "filtered_out": filtered_out if settings.DEBUG else []
            }

        except Exception as e:
            raise Exception(f"YOLO detection failed! (Error: {e})")

yolo_service = YOLOService()
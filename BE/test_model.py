from ultralytics import YOLO
import cv2
import torch
import time

# ===== 1. Kiểm tra GPU =====
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

# ===== 2. Load model =====
model = YOLO("best.pt")

# ===== 3. Chọn device =====
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

# ===== 4. Đường dẫn ảnh =====
image_path = "debug_frames/frame_70.jpg"

# ===== 5. Inference =====
start = time.time()

results = model(
    image_path,
    device=device,
    imgsz=416,     # giảm size → tăng tốc
    conf=0.5,      # lọc object yếu
    half=True      # FP16 (chỉ hoạt động khi dùng GPU)
)

end = time.time()

# ===== 6. Hiển thị ảnh =====
annotated_image = results[0].plot()

cv2.imshow("Result", annotated_image)
cv2.waitKey(0)
cv2.destroyAllWindows()

# ===== 7. In thông tin detect =====
print("\nDetected objects:")
for box in results[0].boxes:
    cls_id = int(box.cls[0])
    conf = float(box.conf[0])
    name = model.names[cls_id]
    print(f"{name}: {conf:.2f}")

# ===== 8. In thời gian xử lý =====
print(f"\nInference time: {(end - start)*1000:.2f} ms")
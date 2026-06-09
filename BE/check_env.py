import platform
import sys
import subprocess
import sqlite3

# =========================
# HÀM HỖ TRỢ
# =========================

def run_command(command):
    """
    Chạy lệnh terminal và trả về kết quả.
    Nếu lỗi thì trả về None.
    """
    try:
        result = subprocess.check_output(
            command,
            shell=True,
            stderr=subprocess.STDOUT
        )
        return result.decode(errors="ignore").strip()
    except Exception:
        return None


def get_cpu_info():
    """
    Lấy thông tin CPU.
    Trên Windows, platform.processor() thường đủ dùng.
    """
    cpu = platform.processor()

    if not cpu:
        cpu = platform.machine()

    return cpu if cpu else "Không xác định"


def get_ram_info():
    """
    Lấy dung lượng RAM bằng psutil.
    Nếu chưa cài psutil thì báo chưa cài.
    """
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        return f"{ram_gb:.2f} GB"
    except ImportError:
        return "Chưa cài psutil"


def get_os_info():
    """
    Lấy thông tin hệ điều hành.
    """
    system = platform.system()
    release = platform.release()
    version = platform.version()

    return f"{system} {release} - build {version}"


def get_python_info():
    """
    Lấy phiên bản Python.
    """
    return sys.version.split()[0]


def get_gpu_info():
    """
    Lấy thông tin GPU NVIDIA bằng nvidia-smi.
    Nếu không có NVIDIA GPU hoặc chưa cài driver thì trả về thông báo.
    """
    gpu_name = run_command(
        "nvidia-smi --query-gpu=name --format=csv,noheader"
    )

    if gpu_name:
        return gpu_name

    return "Không phát hiện GPU NVIDIA hoặc chưa cài NVIDIA Driver"


def get_nvidia_driver_info():
    """
    Lấy phiên bản NVIDIA Driver.
    """
    driver = run_command(
        "nvidia-smi --query-gpu=driver_version --format=csv,noheader"
    )

    if driver:
        return driver

    return "Không có"


def get_cuda_from_nvidia_smi():
    """
    Lấy CUDA Version hiển thị trong nvidia-smi.
    Lưu ý: Đây là CUDA runtime được driver hỗ trợ,
    không nhất thiết là CUDA Toolkit đã cài.
    """
    output = run_command("nvidia-smi")

    if not output:
        return "Không sử dụng CUDA hoặc không có NVIDIA Driver"

    for line in output.splitlines():
        if "CUDA Version" in line:
            try:
                cuda_part = line.split("CUDA Version:")[1]
                cuda_version = cuda_part.split("|")[0].strip()
                return cuda_version
            except Exception:
                return "Có NVIDIA Driver nhưng không đọc được CUDA Version"

    return "Không tìm thấy CUDA Version trong nvidia-smi"


def get_cuda_from_nvcc():
    """
    Lấy CUDA Toolkit bằng nvcc.
    Nếu nvcc không tồn tại thì báo chưa cài CUDA Toolkit hoặc chưa thêm PATH.
    """
    output = run_command("nvcc --version")

    if not output:
        return "Không có nvcc - chưa cài CUDA Toolkit hoặc chưa thêm PATH"

    for line in output.splitlines():
        if "release" in line:
            return line.strip()

    return output


def get_torch_info():
    """
    Kiểm tra PyTorch và CUDA trong PyTorch.
    """
    try:
        import torch

        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
        torch_cuda = torch.version.cuda

        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
        else:
            device_name = "Không sử dụng GPU trong PyTorch"

        return {
            "torch_version": torch_version,
            "cuda_available": cuda_available,
            "torch_cuda": torch_cuda,
            "device_name": device_name
        }

    except ImportError:
        return {
            "torch_version": "Chưa cài PyTorch",
            "cuda_available": False,
            "torch_cuda": "Không có",
            "device_name": "Không có"
        }


def get_ultralytics_info():
    """
    Lấy phiên bản Ultralytics.
    """
    try:
        import ultralytics
        return ultralytics.__version__
    except ImportError:
        return "Chưa cài ultralytics"


def get_fastapi_info():
    """
    Lấy phiên bản FastAPI.
    """
    try:
        import fastapi
        return fastapi.__version__
    except ImportError:
        return "Chưa cài FastAPI"


def get_sqlite_info():
    """
    Lấy phiên bản SQLite.
    """
    return sqlite3.sqlite_version


# =========================
# CHƯƠNG TRÌNH CHÍNH
# =========================

def main():
    cpu = get_cpu_info()
    ram = get_ram_info()
    os_info = get_os_info()
    python_version = get_python_info()

    gpu = get_gpu_info()
    nvidia_driver = get_nvidia_driver_info()
    cuda_driver = get_cuda_from_nvidia_smi()
    cuda_toolkit = get_cuda_from_nvcc()

    torch_info = get_torch_info()
    ultralytics_version = get_ultralytics_info()
    fastapi_version = get_fastapi_info()
    sqlite_version = get_sqlite_info()

    print("=" * 70)
    print("THÔNG TIN MÔI TRƯỜNG THỰC NGHIỆM")
    print("=" * 70)

    print(f"CPU                 : {cpu}")
    print(f"GPU                 : {gpu}")
    print(f"RAM                 : {ram}")
    print(f"Hệ điều hành        : {os_info}")
    print(f"NVIDIA Driver       : {nvidia_driver}")
    print(f"CUDA từ nvidia-smi  : {cuda_driver}")
    print(f"CUDA Toolkit nvcc   : {cuda_toolkit}")
    print(f"Python              : {python_version}")
    print(f"PyTorch             : {torch_info['torch_version']}")
    print(f"PyTorch CUDA        : {torch_info['torch_cuda']}")
    print(f"CUDA khả dụng       : {torch_info['cuda_available']}")
    print(f"Thiết bị PyTorch    : {torch_info['device_name']}")
    print(f"Ultralytics         : YOLO11 - version {ultralytics_version}")
    print(f"Backend             : FastAPI - version {fastapi_version}")
    print(f"Database            : SQLite - version {sqlite_version}")

    print("=" * 70)
    print("BẢNG GỢI Ý ĐỂ ĐƯA VÀO BÁO CÁO")
    print("=" * 70)

    print("| Thành phần | Cấu hình |")
    print("|---|---|")
    print(f"| CPU | {cpu} |")
    print(f"| GPU | {gpu} |")
    print(f"| RAM | {ram} |")
    print(f"| Hệ điều hành | {os_info} |")
    print(f"| CUDA | {cuda_driver} |")
    print(f"| Python | {python_version} |")
    print(f"| Framework AI | Ultralytics YOLO11, version {ultralytics_version} |")
    print(f"| Backend | FastAPI, version {fastapi_version} |")
    print(f"| Database | SQLite, version {sqlite_version} |")

    print("=" * 70)

    if not torch_info["cuda_available"]:
        print("GHI CHÚ:")
        print("PyTorch hiện không sử dụng CUDA. Nếu mô hình chạy được thì khả năng cao đang chạy bằng CPU.")
    else:
        print("GHI CHÚ:")
        print("PyTorch đã nhận CUDA và có thể chạy mô hình trên GPU.")


if __name__ == "__main__":
    main()
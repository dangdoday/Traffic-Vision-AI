# D:\test adcv\Traffic-Vision-AI\src\model_config.py
# Model Configuration
# Định nghĩa các model types và đường dẫn tương ứng

import os
from pathlib import Path

# Base directory - go up one level from src/ to project root
BASE_DIR = Path(__file__).parent  # .../src
MODELS_DIR = BASE_DIR.parent / "models"

# Model types configuration
MODEL_TYPES = {
    "YOLOv8": {
        "folder": "yolov8",
        "description": "YOLOv8 - Fast and accurate",
        # ô tô, xe bus, xe đạp, xe máy, xe tải
        "classes": [0, 1, 2, 3, 4],
        "default_imgsz": 416,
        "default_conf": 0.3,
    },
    "RT-DETR": {
        "folder": "rtdetr",
        "description": "RT-DETR - Transformer-based (Coming soon)",
        # ví dụ mapping khác
        "classes": [0, 1, 2, 5],
        "default_imgsz": 640,
        "default_conf": 0.5,
    },
}


def get_model_folder(model_type: str) -> Path:
    """Lấy đường dẫn folder của model type"""
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unknown model type: {model_type}")

    folder_name = MODEL_TYPES[model_type]["folder"]
    return MODELS_DIR / folder_name


def get_available_weights(model_type: str):
    """Lấy danh sách các file trọng số có sẵn cho model type"""
    model_folder = get_model_folder(model_type)

    if not model_folder.exists():
        return []

    # Tìm tất cả file .pt trong folder
    weight_files = list(model_folder.glob("*.pt"))
    return [f.name for f in weight_files]


def get_weight_path(model_type: str, weight_name: str) -> str:
    """Lấy đường dẫn đầy đủ đến file trọng số"""
    model_folder = get_model_folder(model_type)
    weight_path = model_folder / weight_name

    if not weight_path.exists():
        raise FileNotFoundError(f"Weight file not found: {weight_path}")

    return str(weight_path)


def get_model_config(model_type: str) -> dict:
    """Lấy cấu hình của model type"""
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unknown model type: {model_type}")

    return MODEL_TYPES[model_type]


def scan_all_models() -> dict:
    """Scan tất cả models có sẵn"""
    available_models = {}

    for model_type in MODEL_TYPES.keys():
        weights = get_available_weights(model_type)
        if weights:  # Chỉ thêm vào nếu có weights
            available_models[model_type] = {
                "weights": weights,
                "config": MODEL_TYPES[model_type],
            }

    return available_models


# Auto-detect và chuyển file weight cũ vào folder mới (migration helper)
def migrate_old_weights():
    """Di chuyển file trọng số cũ vào cấu trúc mới"""
    # giả định file cũ nằm ở project root: best_model_12.pt
    old_weight_path = BASE_DIR.parent / "best_model_12.pt"

    if old_weight_path.exists():
        # Tạo folder yolov8 nếu chưa có
        yolov8_folder = MODELS_DIR / "yolov8"
        yolov8_folder.mkdir(parents=True, exist_ok=True)

        # Copy hoặc move file vào folder mới
        new_path = yolov8_folder / "batch16_size416_100epoch.pt"

        if not new_path.exists():
            import shutil

            shutil.copy(old_weight_path, new_path)
            print(f"✅ Migrated old weight to: {new_path}")
            return str(new_path)

    return None

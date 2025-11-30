# Traffic Vision AI

Hệ thống phát hiện vi phạm giao thông sử dụng YOLOv8 và PyQt5.

## 🚀 Chạy ứng dụng

### Cách 1: Sử dụng file chính (Khuyến nghị)
```bash
cd src
python main.py
```

### Cách 2: Phiên bản compact (kế thừa)
```bash
cd src
python main_compact.py
```

Cả 2 đều có đầy đủ tính năng:
- ✅ YOLOv8 detection + ByteTrack
- ✅ Traffic light auto color detection (HSV)
- ✅ Vi phạm đèn đỏ (60 cases luật VN)
- ✅ Direction detection (left/straight/right)
- ✅ Lane violation
- ✅ Config auto-save/load
- ✅ ROI editor với drag & smooth

## 📦 Cấu trúc thư mục

```
src/
├── main.py                    # Entry point chính
├── main_compact.py            # Phiên bản compact (80 dòng)
├── integrated_main.py         # Main window class (3197 dòng)
├── core/                      # Modules modular (reusable)
│   ├── violation_checker.py  # Logic vi phạm
│   ├── traffic_light_classifier.py
│   └── video_thread.py
├── utils/                     # Utilities
│   ├── drawing_utils.py
│   ├── geometry_utils.py
│   └── config_manager.py
└── ui/                        # UI components
    ├── lane_selector.py
    └── overlay_drawer.py
```

## 🎯 Tính năng

- **Detection:** YOLOv8 với ByteTrack tracking
- **Traffic Light:** Tự động phân loại màu (đỏ/vàng/xanh) bằng HSV
- **Violation Detection:** 60 cases theo luật giao thông VN
- **Direction Analysis:** Phân tích hướng di chuyển (trái/thẳng/phải)
- **Config Management:** Tự động lưu/load cấu hình ROIs
- **ROI Editor:** Vẽ, edit, drag, smooth ROIs

## 📝 Requirements

- Python 3.8+
- PyQt5
- OpenCV
- Ultralytics YOLO
- NumPy

## 🔧 Installation

```bash
pip install -r requirements.txt
```

## 📹 Video & Config

- Video: Chọn file MP4/AVI/MOV khi khởi động
- Config: Tự động tìm và load từ `configs/`
- Models: YOLOv8 models trong `models/yolov8/`

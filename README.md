# Traffic-Vision-AI

Traffic-Vision-AI là hệ thống phát hiện vi phạm giao thông từ video, tập trung cho bài toán giao thông Việt Nam. Dự án kết hợp YOLOv8 + ByteTrack + OCR và các ROI cấu hình thủ công để phát hiện vi phạm như vượt đèn đỏ, vượt vạch dừng, sai làn, sai hướng.

## Tính năng chính
- Phát hiện phương tiện + biển số bằng YOLOv8 (classes: car, bus, bicycle, motorbike, truck, license_plate).
- Tracking phương tiện bằng ByteTrack và lưu lịch sử quỹ đạo.
- Nhận diện màu đèn giao thông trong ROI bằng HSV (đỏ/vàng/xanh).
- Cấu hình ROI trực quan: lane, stop line, traffic light, direction ROI, reference vector cho camera nghiêng.
- Kiểm tra vi phạm: vượt đèn đỏ, vượt vạch dừng, sai làn, sai hướng (logic theo luật VN).
- OCR biển số bằng PaddleOCR (có thể tắt/bật trong GUI).
- Hỗ trợ 2 chế độ biển số: YOLO direct hoặc relative tracking.
- Lưu/tải cấu hình theo từng video (tự động load nếu đã có file config).
- GUI PyQt5: chọn model/weights, chỉnh imgsz/conf, chọn CPU/GPU, bật/tắt OCR.

## Pipeline tóm tắt
1. Đọc frame video.
2. YOLOv8 detect phương tiện và biển số.
3. ByteTrack gán track_id và cập nhật quỹ đạo.
4. Map biển số vào phương tiện (YOLO direct hoặc relative tracking).
5. OCR biển số (PaddleOCR) và gán kết quả vào vehicle.
6. Nhận diện màu đèn giao thông từ ROI.
7. Kiểm tra vi phạm (đèn đỏ, vạch dừng, sai làn, sai hướng).
8. Vẽ overlay và hiển thị thống kê trên GUI.

## Yêu cầu
- Python 3.8+ (khuyến nghị 3.10+)
- Windows / Linux / macOS
- CUDA nếu cần realtime

## Cài đặt
```bash
git clone https://github.com/dangdoday/Traffic-Vision-AI.git
cd Traffic-Vision-AI

python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

pip install -r requirements.txt
```

### GPU (tùy chọn)
```bash
# Chọn đúng CUDA version phù hợp với máy
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install paddlepaddle-gpu
```

## Chạy ứng dụng (GUI)
```bash
python src/integrated_main.py
```

## Quy trình cấu hình nhanh
1. Chọn video khi app mở.
2. (Khuyến nghị) Set Reference Vector để xác định hướng "đi thẳng".
3. Vẽ Stop Line.
4. Add Traffic Light ROI (chọn loại đèn phù hợp).
5. Vẽ Lane polygons và chọn loại xe được phép.
6. Vẽ Direction ROI và chọn hướng được phép.
7. Save config (Ctrl+S).
8. Start Detection (Space).

## Cấu hình JSON
File config nằm trong `configs/<video>_config.json` và tự động load lại khi mở cùng video.

```json
{
  "video_name": "video.mp4",
  "lanes": [
    {
      "points": [[x1, y1], [x2, y2], [x3, y3]],
      "label": "Lane 1",
      "allowed_types": [0, 3]
    }
  ],
  "stopline": { "p1": [x1, y1], "p2": [x2, y2] },
  "traffic_lights": [
    { "x1": 100, "y1": 50, "x2": 140, "y2": 120, "type": "tròn", "color": "đỏ" }
  ],
  "direction_zones": [
    {
      "name": "roi_1",
      "points": [[x1, y1], [x2, y2], [x3, y3]],
      "allowed_directions": ["left", "straight"],
      "primary_direction": "left"
    }
  ],
  "reference_vector": { "p1": [x1, y1], "p2": [x2, y2] },
  "model": { "type": "YOLOv8", "weight": "416_vehicle_plate.pt", "imgsz": 416, "conf_threshold": 0.3 }
}
```

### Mapping class
- 0: ô tô
- 1: xe bus
- 2: xe đạp
- 3: xe máy
- 4: xe tải
- 5: biển số

## Models
- Weights nằm trong `models/yolov8/`.
- App tự động scan file `.pt` và hiển thị trong menu.
- Có sẵn: `batch16_size416_100epoch.pt`, `batch64_size640_100epoch.pt`, `416_vehicle_plate.pt`.

## OCR và test nhanh
GUI sử dụng PaddleOCR (có thể tắt/bật).

Script test OCR:
```bash
python test_ocr.py
```
Script sẽ cho phép chọn ảnh, chạy YOLO và OCR, sau đó in kết quả biển số.

## Tools (CLI)
- Vẽ direction ROI ngoài GUI:
  ```bash
  python src/tools/roi_direction_editor.py --video path/to/video.mp4
  ```
- Xác định reference vector:
  ```bash
  python src/tools/reference_vector_calibrator.py --video path/to/video.mp4
  ```

## Cấu trúc thư mục
```
Traffic-Vision-AI/
  src/
    integrated_main.py
    core/
    app/
    handlers/
    ui/
    tools/
    utils/
  models/
  configs/
  docs/
  Figures/
  requirements.txt
  SYSTEM_PIPELINE.md
```

## Tài liệu
- `SYSTEM_PIPELINE.md`: mô tả pipeline tổng quan.
- `docs/COMPLETE_VIOLATION_CASES.md`: 60 tình huống vi phạm theo luật VN.
- `docs/COMPLETE_LOGIC_ANALYSIS.md`: phân tích logic vi phạm.
- `docs/DIRECTION_DETECTION.md`: hệ thống nhận diện hướng.
- `docs/DIRECTION_INTEGRATION_GUIDE.md`: hướng dẫn tích hợp.
- `docs/TRAFFIC_LIGHT_RULES_VN.md`: quy định đèn giao thông VN.

## Góp ý
Nếu gặp lỗi hoặc muốn đóng góp, vui lòng tạo issue trên GitHub.

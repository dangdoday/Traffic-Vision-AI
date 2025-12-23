# YOLOv8 Models

Thư mục chứa các trọng số YOLOv8 để detect phương tiện.

## Các model hiện có:

- `batch16_size416_100epoch.pt` - Custom trained model
  - Batch size: 16
  - Image size: 416x416
  - Epochs: 100
  - Classes: ô tô, xe máy, xe tải, xe bus

## Hướng dẫn thêm model mới:

1. Copy file .pt vào folder này
2. Đặt tên file theo format: `batch{batch}_size{size}_{epochs}epoch.pt`
3. Khởi động lại app để model xuất hiện trong dropdown

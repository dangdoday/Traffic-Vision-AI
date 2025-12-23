# Models Directory

Thư mục chứa các file trọng số (weights) cho các model khác nhau.

## Cấu trúc:

```
models/
├── yolov8/          # YOLOv8 weights
│   ├── batch16_size416_100epoch.pt
│   └── batch64_size640_100epoch.pt
├── rtdetr/          # RT-DETR weights (future)
│   └── rtdetr-l.pt
└── README.md
```

## Hướng dẫn sử dụng:

1. Đặt file trọng số vào folder tương ứng với loại model
2. Chọn model từ giao diện
3. Hệ thống tự động load trọng số từ folder đúng

## Lưu ý:

- File trọng số phải có định dạng `.pt` (PyTorch)
- Tên file nên mô tả rõ cấu hình model (batch size, image size, epochs)

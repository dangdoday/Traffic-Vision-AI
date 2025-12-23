# Hướng Dẫn Sử Dụng Direction Detection

## ✅ Đã Tích Hợp Thành Công!

Direction Detection đã được tích hợp vào `integrated_main.py`.

## 🎯 Cách Sử Dụng

### 1. **Chọn Hướng (Không Cần Bấm Phím!)**

Sử dụng dropdown "Direction" trong UI:
- **left** → Vẽ ROI cho hướng rẽ trái (màu đỏ 🔴)
- **straight** → Vẽ ROI cho hướng đi thẳng (màu xanh 🟢)
- **right** → Vẽ ROI cho hướng rẽ phải (màu vàng 🟡)

### 2. **Vẽ Direction ROI**

1. Click dropdown **"Direction"**, chọn hướng (left/straight/right)
2. Click nút **"Draw Direction ROI (Click points)"**
3. Click chuột trên video để đánh dấu các điểm của polygon
4. Click nút **"Finish Direction ROI"** khi xong

### 3. **Quản Lý Direction ROIs**

- **Xem danh sách**: ROIs hiển thị trong list với icon màu
  - 🔴 ROI 1: LEFT (26 pts)
  - 🟢 ROI 2: STRAIGHT (15 pts)
  - 🟡 ROI 3: RIGHT (38 pts)

- **Xóa ROI**: Chọn ROI trong list → Click "Delete Selected Direction ROI"

- **Lưu ROIs**: Click "Save Direction ROIs to JSON"
  - Lưu thành file `video_name_direction_rois.json`
  - Format chuẩn để sử dụng sau này

- **Load ROIs**: Click "Load Direction ROIs from JSON"
  - Tải lại các ROIs đã vẽ trước đó

- **Ẩn/Hiện ROIs**: Toggle "Show Direction ROIs: ON/OFF"

## 📦 Tính Năng Mới

### ✅ Giao Diện UI Hoàn Chỉnh

```
┌─────────────────────────────────────┐
│ Direction ROI Management            │
├─────────────────────────────────────┤
│ Direction: [left ▼]                 │  ← Dropdown chọn hướng
│                                     │
│ [Draw Direction ROI (Click points)] │  ← Bắt đầu vẽ
│ [Finish Direction ROI]               │  ← Kết thúc ROI
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 🔴 ROI 1: LEFT (26 pts)        │ │  ← List ROIs
│ │ 🟡 ROI 2: RIGHT (38 pts)       │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Delete Selected Direction ROI]     │
│ [Save Direction ROIs to JSON]       │
│ [Load Direction ROIs from JSON]     │
│ [Show Direction ROIs: ON]           │  ← Toggle hiển thị
└─────────────────────────────────────┘
```

### ✅ Hiển Thị Trực Quan

- **ROIs được vẽ với màu sắc:**
  - Đỏ (0, 0, 255): LEFT
  - Xanh (0, 255, 0): STRAIGHT
  - Vàng (0, 165, 255): RIGHT

- **Transparency 25%**: Nhìn rõ cả đường và ROI

- **Label ở giữa ROI**: Hiển thị "LEFT", "RIGHT", "STRAIGHT"

## 🚀 Workflow Hoàn Chỉnh

### Bước 1: Vẽ ROIs cho tất cả hướng
```
1. Chọn "left" → Draw ROI cho làn rẽ trái
2. Chọn "straight" → Draw ROI cho làn đi thẳng  
3. Chọn "right" → Draw ROI cho làn rẽ phải
```

### Bước 2: Lưu ROIs
```
Click "Save Direction ROIs to JSON"
→ Lưu thành "video_name_direction_rois.json"
```

### Bước 3: Start Detection
```
Click "Start Detection"
→ Hệ thống sẽ:
  - Phát hiện xe (YOLO)
  - Xác định xe trong ROI nào (ROI-based)
  - Tính toán vector chuyển động (Trajectory-based)
  - Kết hợp 2 nguồn (Fusion)
  - Hiển thị hướng cuối cùng
```

## 📊 Output Mẫu

Console sẽ hiển thị:
```
✅ Created Direction ROI #1: LEFT (26 points)
✅ Created Direction ROI #2: RIGHT (38 points)
📊 Display FPS: 30 | Detection FPS: 25

# Khi có detection:
🚗 Vehicle 123 (car):
   ROI: left
   Trajectory: left (confidence: 0.85)
   Final: LEFT ✅ (source: both)
```

## 🎨 Màu Sắc Coding

| Hướng | Màu | RGB | Icon |
|-------|-----|-----|------|
| LEFT | Đỏ | (0, 0, 255) | 🔴 |
| STRAIGHT | Xanh | (0, 255, 0) | 🟢 |
| RIGHT | Vàng | (0, 165, 255) | 🟡 |

## 💾 Format JSON

```json
{
  "video": "traffic.mp4",
  "frame_shape": [1080, 1920],
  "rois": [
    {
      "name": "roi_1",
      "points": [[425, 273], [472, 232], ...],
      "direction": "left"
    },
    {
      "name": "roi_2",
      "points": [[1591, 875], [1490, 733], ...],
      "direction": "right"
    }
  ]
}
```

## 🔧 Tích Hợp Backend (Sắp Tới)

Module Direction Detection đã sẵn sàng, cần thêm vào VideoThread:

1. ✅ ROI Manager: Kiểm tra điểm trong polygon
2. ✅ Trajectory Analyzer: Tính góc từ history
3. ✅ Direction Fusion: Kết hợp 2 nguồn
4. ⏳ Tích hợp vào process_detection() của VideoThread

## 📝 Next Steps

1. **Test với video thật**: Vẽ ROIs và xem kết quả
2. **Điều chỉnh tham số**: Angle threshold, history size
3. **Tích hợp vào detection**: Hiển thị direction trên mỗi vehicle
4. **Validation logic**: Kết hợp với traffic light violation

## 🎯 Lợi Ích So Với Keyboard

| Trước (Keyboard) | Sau (UI Dropdown) |
|------------------|-------------------|
| Nhấn `1`, `2`, `3` | Click dropdown chọn |
| Dễ nhầm phím | Giao diện rõ ràng |
| Không thấy đang chọn gì | Hiển thị tên hướng |
| Khó dùng cho người mới | Trực quan, dễ học |

## ✨ Hoàn Thành

✅ Tích hợp Direction Detection vào integrated_main.py  
✅ UI hoàn chỉnh với dropdown thay vì keyboard  
✅ Save/Load JSON  
✅ Toggle show/hide ROIs  
✅ Hiển thị trực quan với màu sắc  
✅ Ready để tích hợp backend direction analysis  

**Chương trình đang chạy thành công! 🎉**

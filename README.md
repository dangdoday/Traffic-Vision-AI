# Traffic Violation by dangdoday

Hệ thống phát hiện vi phạm giao thông thông minh sử dụng YOLOv8, ByteTrack và PyQt5.

## 📋 Mục lục
- [Cài đặt](#-cài-đặt)
- [Chạy ứng dụng](#-chạy-ứng-dụng)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
- [Tính năng](#-tính-năng)
- [Phím tắt](#-phím-tắt)

## 🛠️ Cài đặt

### Yêu cầu hệ thống
- Python 3.8+
- Windows/Linux/MacOS
- RAM: 8GB+

### Cài đặt thư viện

```bash
pip install -r requirements.txt
```

Các thư viện chính:
- `ultralytics` - YOLOv8
- `opencv-python` - Xử lý video/hình ảnh
- `PyQt5` - Giao diện đồ họa
- `numpy` - Tính toán số học

## 🚀 Chạy ứng dụng

```bash
cd src
python main.py
```

Hoặc sử dụng phiên bản compact (80 dòng, kế thừa):
```bash
cd src
python main_compact.py
```

## 📖 Hướng dẫn sử dụng

### 1️⃣ Khởi động và chọn video

1. **Chọn video**: Menu `File → Select Video` hoặc nút "Select Video File"
2. **Chọn model YOLO**: Mặc định sử dụng YOLOv8n (nhanh) hoặc YOLOv8s (chính xác hơn)
3. Ứng dụng sẽ tự động tải cấu hình nếu đã lưu trước đó

### 2️⃣ Cấu hình Reference Vector (Bắt buộc)

**Reference Vector** là vector tham chiếu cho camera nghiêng, giúp xác định hướng di chuyển chính xác.

1. Menu `Draw → Set Reference Vector` hoặc nút "Set Reference Vector"
2. Click **2 điểm** trên làn đường thẳng theo hướng lưu lượng giao thông
3. Ví dụ: Điểm đầu làn → Điểm cuối làn (theo chiều xe chạy)

> ⚠️ **Quan trọng**: Reference Vector ảnh hưởng đến độ chính xác phát hiện hướng (left/straight/right)

### 3️⃣ Vẽ Lane (Làn đường vi phạm)

**Lane** là vùng làn đường để phát hiện xe đi sai làn.

1. Menu `Draw → Draw Lane` hoặc nút "Add Lane"
2. Click nhiều điểm trên video để tạo polygon bao quanh làn đường
3. Double-click điểm cuối để hoàn tất
4. Chọn loại xe được phép đi vào làn:
   - ✅ All vehicles
   - ✅ Xe máy
   - ✅ Ô tô
   - ✅ Xe bus
   - ✅ Xe tải

**Chỉnh sửa Lane:**
- Menu `Edit → Edit Lane` → Chọn lane cần sửa
- **Kéo thả điểm**: Left-click + drag
- **Thêm điểm**: Double-click gần cạnh
- **Xóa điểm**: Right-click trên điểm (tối thiểu 3 điểm)
- **Hoàn tất**: Nhấn `Enter` → Cấu hình loại xe

### 4️⃣ Vẽ Stop Line (Vạch dừng)

**Stop Line** là vạch dừng đèn đỏ (chỉ cần 1 đường).

1. Menu `Draw → Set Stop Line` hoặc nút "Set Stop Line"
2. Click **2 điểm** để tạo đường thẳng

### 5️⃣ Thêm Traffic Light (Đèn tín hiệu)

**Traffic Light ROI** là vùng chứa đèn giao thông để phát hiện màu tự động.

1. Menu `Draw → Add Traffic Light` hoặc nút "Add Traffic Light"
2. Click **2 điểm** để vẽ hình chữ nhật bao quanh đèn
3. Chọn loại đèn:
   - **Normal**: Đèn thường (3 màu)
   - **Arrow Left**: Đèn rẽ trái
   - **Arrow Straight**: Đèn đi thẳng
   - **Arrow Right**: Đèn rẽ phải

> 💡 Hệ thống tự động phát hiện màu đèn bằng HSV color tracking

### 6️⃣ Vẽ Direction ROI (Vùng phát hiện hướng)

**Direction ROI** là vùng để phát hiện xe đi sai hướng (vi phạm đèn đỏ theo hướng).

1. Menu `Draw → Draw Direction ROI`
2. Click nhiều điểm để tạo polygon bao quanh vùng
3. Double-click để hoàn tất
4. Nhấn nút "Finish Direction ROI"

**Chỉnh sửa Direction ROI:**
- Menu `Edit → Edit Direction ROI` → Chọn ROI cần sửa
- **Kéo thả điểm**: Left-click + drag
- **Thêm điểm**: Double-click gần cạnh
- **Xóa điểm**: Right-click trên điểm
- **Hoàn tất**: Nhấn `Enter` → Cấu hình hướng đi

**Cấu hình hướng đi (sau khi nhấn Enter):**
- Chọn các hướng được phép: ⬅️ Rẽ trái / ⬆️ Đi thẳng / ➡️ Rẽ phải
- Chọn hướng chính (primary direction) cho màu hiển thị:
  - 🔴 Left (Red)
  - 🟢 Straight (Green)
  - 🟡 Right (Yellow)

### 7️⃣ Bắt đầu phát hiện

1. Nhấn nút **"Start Detection"**
2. Video sẽ bắt đầu phát hiện vi phạm:
   - 🔴 Hộp đỏ + **[LANE]**: Vi phạm làn đường
   - 🔴 Hộp đỏ + **[RED LIGHT]**: Vượt đèn đỏ (sau stopline)
   - 🟦 Hộp xanh: Xe bình thường

### 8️⃣ Lưu và tải cấu hình

**Lưu tự động:**
- Cấu hình được lưu tự động theo tên video vào thư mục `configs/`

**Lưu thủ công:**
- Menu `File → Save Config` → Chọn vị trí lưu

**Tải cấu hình:**
- Menu `File → Load Config` → Chọn file `.json`

## 🎯 Tính năng

### Phát hiện vi phạm
- ✅ **Lane Violation**: Xe đi sai làn (theo loại xe)
- ✅ **Red Light Violation**: Vượt đèn đỏ (60 cases theo luật Việt Nam)
- ✅ **Direction Detection**: Phát hiện hướng đi (left/straight/right)

### Công nghệ
- ✅ **YOLOv8**: Object detection (xe máy, ô tô, xe bus, xe tải)
- ✅ **ByteTrack**: Tracking đa đối tượng
- ✅ **HSV Color Tracking**: Tự động phát hiện màu đèn giao thông
- ✅ **Multi-direction ROI**: Hỗ trợ nhiều hướng đi trong 1 ROI

### Giao diện
- ✅ **Interactive ROI Editor**: Kéo thả, thêm, xóa điểm dễ dàng
- ✅ **View Toggles**: Bật/tắt hiển thị lanes, stopline, traffic lights, reference vector
- ✅ **Auto Save/Load**: Tự động lưu và tải cấu hình theo video
- ✅ **Real-time FPS Display**: Hiển thị FPS detection và display

## ⌨️ Phím tắt

### Chế độ vẽ
- **Double-click**: Thêm điểm mới (khi đang vẽ ROI)
- **Enter**: Hoàn tất chỉnh sửa (Lane/ROI)
- **Delete**: Hiển thị hướng dẫn xóa điểm
- **Right-click**: Xóa điểm (khi đang chỉnh sửa)

### View toggles
- **Ctrl+L**: Toggle hiển thị Lanes
- **Ctrl+P**: Toggle hiển thị Stop Line
- **Ctrl+T**: Toggle hiển thị Traffic Lights
- **Ctrl+V**: Toggle hiển thị Reference Vector

### Menu
- **File**: Open Video, Save/Load Config
- **Draw**: Vẽ Lane, Stop Line, Traffic Light, Direction ROI, Reference Vector
- **Edit**: Chỉnh sửa Lane, ROI, Smooth ROI, Change Directions
- **Delete**: Xóa Lane, Stop Line, Traffic Light, Direction ROI
- **View**: Toggle hiển thị các thành phần
- **Settings**: Cài đặt FPS, realtime mode
- **Help**: Shortcuts, About

## 📊 Cấu trúc thư mục

```
Traffic-Vision-AI/
├── src/
│   ├── main.py                    # Entry point chính
│   ├── main_compact.py            # Phiên bản compact (80 dòng)
│   ├── integrated_main.py         # Main window (3800+ dòng)
│   ├── core/                      # Core modules
│   │   ├── violation_checker.py
│   │   ├── traffic_light_classifier.py
│   │   ├── app_state.py
│   │   └── video_thread.py
│   ├── utils/                     # Utilities
│   │   ├── drawing_utils.py
│   │   ├── geometry_utils.py
│   │   └── config_manager.py
│   └── tools/                     # Tools
│       └── roi_editor.py          # Interactive ROI editor
├── configs/                       # Auto-saved configs
├── models/                        # YOLO models
└── README.md
```

## 🐛 Xử lý lỗi thường gặp

### 1. Không phát hiện được hướng đi
- ✅ Kiểm tra **Reference Vector** đã vẽ đúng chưa
- ✅ Reference Vector phải nằm trên làn đường **thẳng**
- ✅ Hướng từ điểm 1 → điểm 2 phải theo chiều xe chạy

### 2. Đèn giao thông không đổi màu
- ✅ ROI đèn giao thông phải bao đúng vùng đèn
- ✅ Không để ROI quá rộng (chỉ bao đèn)
- ✅ Kiểm tra ánh sáng video có đủ rõ không

### 3. Vi phạm lane không hiển thị
- ✅ Kiểm tra loại xe có trong danh sách allowed của lane không
- ✅ Lane polygon phải bao đúng vùng làn đường

### 4. FPS thấp
- ✅ Giảm resolution video
- ✅ Sử dụng YOLOv8n thay vì YOLOv8s
- ✅ Bật "Realtime Mode" trong Settings
- ✅ Sử dụng GPU nếu có

## 👨‍💻 Tác giả

**dangdoday**
- GitHub: [@dangdoday](https://github.com/dangdoday)
- Repository: [Traffic-Vision-AI](https://github.com/dangdoday/Traffic-Vision-AI)

## 📝 License

Version 2.0 - Advanced Traffic Violation Detection System

---

💡 **Tip**: Xem video demo và hướng dẫn chi tiết tại [GitHub Repository](https://github.com/dangdoday/Traffic-Vision-AI)
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

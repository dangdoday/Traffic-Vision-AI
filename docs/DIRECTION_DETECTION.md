# Hệ Thống Nhận Diện Hướng Di Chuyển cho Giao Thông Việt Nam

## 📋 Tổng Quan

Hệ thống nhận diện hướng di chuyển (rẽ trái, rẽ phải, đi thẳng) cho xe trong môi trường giao thông đông đúc Việt Nam, nơi xe không đi theo làn cố định.

### 🎯 Đặc Điểm

- ✅ **ROI-based Direction**: Chia vùng theo hướng đi, không phụ thuộc lane-line
- ✅ **Trajectory-based Direction**: Phân tích vector chuyển động từ lịch sử vị trí
- ✅ **Direction Fusion**: Kết hợp 2 nguồn thông tin để ra quyết định cuối cùng
- ✅ **Conflict Detection**: Phát hiện khi xe đi sai hướng so với ROI
- ✅ **Visual Editor**: Tool vẽ ROI thủ công với giao diện trực quan

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────────────────┐
│                    VIDEO INPUT                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              YOLO Detection + ByteTrack                      │
│  Output: track_id, bbox (x1,y1,x2,y2), class                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────────┐
│  ROI Manager    │    │ Trajectory Analyzer  │
│                 │    │                      │
│ • Load ROIs     │    │ • Track positions    │
│ • Check point   │    │ • Calculate angle    │
│   in polygon    │    │ • Classify direction │
│ • Get direction │    │ • Compute confidence │
└────────┬────────┘    └──────────┬───────────┘
         │                        │
         │  roi_direction         │  trajectory_direction
         │                        │  + confidence
         └───────────┬────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Direction Fusion     │
         │                       │
         │ • Combine sources     │
         │ • Detect conflicts    │
         │ • Final decision      │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   FINAL DIRECTION     │
         │  left / right /       │
         │  straight / unknown   │
         └───────────────────────┘
```

---

## 📦 Các Module

### 1. **ROI Direction Editor** (`tools/roi_direction_editor.py`)

Tool vẽ ROI thủ công với giao diện OpenCV.

**Chức năng:**
- Load frame đầu từ video
- Click chuột để vẽ polygon
- Gán nhãn: left (1), straight (2), right (3)
- Nhấn `N` để kết thúc ROI
- Nhấn `S` để lưu JSON
- Nhấn `D` để xóa ROI cuối

**Output:** `rois_direction.json`
```json
{
  "video": "traffic.mp4",
  "frame_shape": [1080, 1920],
  "rois": [
    {
      "name": "roi_1",
      "points": [[100, 200], [150, 200], [150, 400], [100, 400]],
      "direction": "left"
    }
  ]
}
```

**Usage:**
```bash
python src/tools/roi_direction_editor.py --video path/to/video.mp4
```

---

### 2. **ROI Direction Manager** (`core/roi_direction_manager.py`)

Quản lý ROIs và xác định hướng dựa trên vị trí.

**Key Methods:**
- `load_rois(json_path)`: Load ROIs từ file
- `get_roi_direction(cx, cy)`: Trả về direction của ROI chứa điểm (cx, cy)
- `draw_rois(frame)`: Vẽ ROIs lên frame
- `get_statistics()`: Thống kê số lượng ROIs

**Principle:**
Sử dụng `cv2.pointPolygonTest()` để kiểm tra điểm có nằm trong polygon không.

```python
result = cv2.pointPolygonTest(polygon, (cx, cy), False)
# result >= 0: inside or on edge
# result < 0: outside
```

---

### 3. **Trajectory Direction Analyzer** (`core/trajectory_direction_analyzer.py`)

Phân tích hướng từ motion vector của vehicle.

**Algorithm:**

1. **Lưu lịch sử N vị trí gần nhất** (default: 15 points)
```python
trajectories[track_id] = deque([(x1, y1), (x2, y2), ...], maxlen=15)
```

2. **Tính góc chuyển hướng từ các vector liên tiếp**

Với 3 điểm liên tiếp: P1, P2, P3
- Vector v1 = P2 - P1
- Vector v2 = P3 - P2
- Góc = atan2(cross_product, dot_product)

```python
cross = v1[0] * v2[1] - v1[1] * v2[0]  # z-component
dot = v1[0] * v2[0] + v1[1] * v2[1]
angle = atan2(cross, dot)  # radian → degrees
```

3. **Trung bình có trọng số** (ưu tiên góc gần đây)

4. **Phân loại:**
- `angle > +25°` → **right**
- `angle < -25°` → **left**
- `-25° ≤ angle ≤ +25°` → **straight**

**Key Methods:**
- `update_position(track_id, cx, cy)`: Cập nhật vị trí
- `get_trajectory_direction(track_id)`: Tính hướng
- `get_trajectory_info(track_id)`: Lấy chi tiết (angle, confidence)
- `draw_trajectory(frame, track_id)`: Vẽ đường đi

---

### 4. **Direction Fusion** (`core/direction_fusion.py`)

Kết hợp ROI-based và Trajectory-based để ra quyết định cuối cùng.

**Logic:**

| ROI Direction | Trajectory Direction | Trajectory Confidence | Decision | Source |
|--------------|---------------------|----------------------|----------|--------|
| None | unknown | - | unknown | none |
| left | unknown | - | **left** | roi |
| None | right | high | **right** | trajectory |
| left | left | high | **left** | both ✅ |
| left | straight | low | **left** | roi |
| left | right | high | **right** ⚠️ conflict | trajectory |

**Nguyên tắc:**
1. Nếu chỉ có 1 nguồn → dùng nguồn đó
2. Nếu cả 2 giống nhau → perfect match
3. Nếu trajectory confidence thấp → tin ROI
4. Nếu conflict + trajectory confidence cao → **ưu tiên trajectory** (xe có thể đi lệch ROI)

**Key Methods:**
```python
final_direction, source, is_conflict = fusion.fuse_directions(
    roi_direction='left',
    trajectory_direction='straight',
    trajectory_confidence=0.85
)
# → ('straight', 'trajectory', True)
```

---

## 🚀 Sử dụng

### Step 1: Vẽ ROIs

```bash
python src/tools/roi_direction_editor.py --video traffic_video.mp4
```

Thao tác:
1. Click chuột để vẽ polygon
2. Nhấn `1` (left), `2` (straight), `3` (right) để chọn hướng
3. Nhấn `N` để hoàn thành ROI
4. Nhấn `S` để lưu file `rois_direction.json`

### Step 2: Tích hợp vào pipeline

```python
from core.roi_direction_manager import ROIDirectionManager
from core.trajectory_direction_analyzer import TrajectoryDirectionAnalyzer
from core.direction_fusion import DirectionFusion

# Initialize
roi_manager = ROIDirectionManager("rois_direction.json")
trajectory_analyzer = TrajectoryDirectionAnalyzer(history_size=15)
fusion = DirectionFusion()

# Trong vòng lặp xử lý video
for detection in detections:  # từ YOLO + ByteTrack
    track_id, bbox, class_name = detection
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    
    # 1. ROI direction
    roi_dir = roi_manager.get_roi_direction(cx, cy)
    
    # 2. Trajectory direction
    trajectory_analyzer.update_position(track_id, cx, cy)
    traj_info = trajectory_analyzer.get_trajectory_info(track_id)
    
    # 3. Fuse
    final_dir, source, conflict = fusion.fuse_directions(
        roi_dir, 
        traj_info['direction'], 
        traj_info['confidence']
    )
    
    # 4. Vẽ lên frame
    color = (0, 255, 0) if final_dir == 'straight' else \
            (0, 165, 255) if final_dir == 'right' else (0, 0, 255)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, f"{final_dir.upper()}", (x1, y1-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
```

### Step 3: Chạy demo

```python
python src/demo_direction_detection.py
```

---

## 🎨 Màu Sắc

| Hướng | Màu | RGB |
|-------|-----|-----|
| **Đi thẳng (straight)** | 🟢 Xanh lá | (0, 255, 0) |
| **Rẽ phải (right)** | 🟡 Vàng | (0, 165, 255) |
| **Rẽ trái (left)** | 🔴 Đỏ | (0, 0, 255) |
| **Chưa xác định (unknown)** | ⚪ Xám | (128, 128, 128) |

---

## 🧠 Nguyên Lý Phù Hợp với Giao Thông Việt Nam

### ❌ Tại sao **KHÔNG** dùng Lane-Line Detection?

**Vấn đề của lane-line:**
1. **Xe không đi theo làn**: Trong giao thông VN, xe máy, ô tô thường đi chéo làn, chen lấn
2. **Nhiễu cao**: Vạch kẻ đường mờ, bị che khuất, không rõ ràng
3. **Phụ thuộc góc camera**: Phải calibrate chính xác, khó khăn khi deploy
4. **Không linh hoạt**: Không xử lý được giao lộ phức tạp, đường cong

### ✅ Tại sao **ROI + Trajectory** phù hợp?

#### 1. **ROI-based: Linh hoạt với bất kỳ layout đường nào**

- Vẽ ROI theo **hướng di chuyển thực tế** chứ không phải làn đường vật lý
- Có thể vẽ ROI cho giao lộ phức tạp (5-6 ngã)
- Không cần vạch kẻ đường rõ ràng

**Ví dụ:**
```
        ┌─────────┐
        │ ROI_1   │ (straight)
        │ (xanh)  │
┌───────┼─────────┼───────┐
│ ROI_2 │         │ ROI_3 │
│ (đỏ)  │  Giao   │ (vàng)│
│ left  │  lộ     │ right │
└───────┴─────────┴───────┘
```

Xe ở đâu → xác định hướng dự kiến là gì.

#### 2. **Trajectory-based: Robust với xe đi lệch ROI**

**Tình huống thực tế:**
- Xe định rẽ phải nhưng đang ở làn trái (ROI left)
- Xe chuyển làn đột ngột
- Xe máy chen lấn giữa các xe

**Giải pháp:**
- Trajectory phân tích **vector chuyển động thực tế**
- Không quan tâm xe đang ở làn nào
- Chỉ xem xe **đang đi về hướng nào**

**Công thức:**
```python
# Từ lịch sử 15 điểm gần nhất
# Tính góc chuyển hướng trung bình
# Nếu góc > 25° → đang rẽ phải (dù đang ở làn trái!)
```

#### 3. **Fusion: Kết hợp tốt nhất của cả 2**

**Case 1: Xe đi đúng ROI**
- ROI = straight, Trajectory = straight
- → **Quyết định: straight** ✅ (source: both)

**Case 2: Xe chưa di chuyển đủ (trajectory chưa rõ)**
- ROI = left, Trajectory = unknown (confidence thấp)
- → **Quyết định: left** (source: roi)

**Case 3: Xe đi lệch ROI (conflict)**
- ROI = left, Trajectory = right (confidence cao)
- → **Quyết định: right** ⚠️ (source: trajectory)
- Log warning: "Vehicle deviating from expected ROI"

### 🎯 So sánh với Lane-Line

| Tiêu chí | Lane-Line | ROI + Trajectory |
|----------|-----------|------------------|
| **Yêu cầu vạch kẻ rõ** | ✅ Bắt buộc | ❌ Không cần |
| **Xe đi đúng làn** | ✅ Bắt buộc | ❌ Không cần |
| **Xử lý giao lộ phức tạp** | ❌ Khó | ✅ Dễ dàng |
| **Xử lý xe lệch làn** | ❌ Fail | ✅ Robust |
| **Setup effort** | 🔴 Cao (calibration) | 🟢 Thấp (vẽ ROI) |
| **Phù hợp VN** | ❌ Không | ✅ Rất phù hợp |

---

## 📊 Minh Họa Trực Quan

### Giao lộ 4 ngã với ROIs

```
                  ↑ NORTH
                  │
        ┌─────────┼─────────┐
        │         │         │
        │   ROI   │   ROI   │
        │  NORTH  │  NORTH  │
        │ (green) │ (green) │
        │         │         │
   WEST ├─────────┼─────────┤ EAST
   ←────┤   ROI   │   ROI   ├────→
        │  WEST   │  EAST   │
        │  (red)  │ (yellow)│
        │         │         │
        │   ROI   │   ROI   │
        │  SOUTH  │  SOUTH  │
        │ (green) │ (green) │
        │         │         │
        └─────────┼─────────┘
                  │
                  ↓ SOUTH
```

### Trajectory Analysis

```
Frame 1:    ●                  (start)
Frame 2:      ●
Frame 3:        ●
Frame 4:          ●
Frame 5:            ●→         (end)

Vector: →  (góc ≈ 0°)
Direction: STRAIGHT ✅
```

```
Frame 1:    ●                  (start)
Frame 2:      ●
Frame 3:         ●
Frame 4:            ●
Frame 5:               ●       (end)
                         ↘

Vector: ↘  (góc ≈ +35°)
Direction: RIGHT ✅
```

```
Frame 1:               ●       (start)
Frame 2:            ●
Frame 3:         ●
Frame 4:      ●
Frame 5:    ●                  (end)
          ↙

Vector: ↙  (góc ≈ -40°)
Direction: LEFT ✅
```

---

## 🔬 Tham Số Điều Chỉnh

### TrajectoryDirectionAnalyzer

```python
TrajectoryDirectionAnalyzer(
    history_size=15,        # Số điểm lưu (5-20)
    min_points=5,           # Điểm tối thiểu để tính (3-10)
    angle_threshold=25.0    # Ngưỡng góc phân loại (15-35°)
)
```

**Gợi ý:**
- **Traffic nhanh** (cao tốc): `history_size=10`, `angle_threshold=20`
- **Traffic chậm** (thành phố): `history_size=20`, `angle_threshold=30`
- **Giao lộ phức tạp**: `min_points=8`, `angle_threshold=25`

### DirectionFusion

```python
DirectionFusion(
    trajectory_weight=0.7,           # Trọng số trajectory (0.5-0.9)
    min_trajectory_confidence=0.5    # Ngưỡng tin cậy (0.3-0.7)
)
```

**Gợi ý:**
- **Tin ROI hơn**: `trajectory_weight=0.5`, `min_confidence=0.7`
- **Tin trajectory hơn**: `trajectory_weight=0.8`, `min_confidence=0.4`

---

## 📝 Logging & Debug

Hệ thống có logging chi tiết:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Output mẫu:**
```
✅ Đã load 3 ROIs từ rois_direction.json
   - LEFT: 1
   - STRAIGHT: 1
   - RIGHT: 1

DEBUG:DirectionFusion:ROI and trajectory agree: straight
DEBUG:TrajectoryDirectionAnalyzer:Trajectory: straight (angle=2.3°, conf=0.85)

⚠️  Direction conflict: ROI=left, Trajectory=right (conf=0.78)
    → Using trajectory (vehicle may deviate from ROI)
```

---

## 🎯 Kết Luận

Hệ thống **ROI + Trajectory** là giải pháp tối ưu cho giao thông Việt Nam vì:

1. ✅ **Không phụ thuộc lane-line** (vạch kẻ đường)
2. ✅ **Robust với xe đi lệch làn** (trajectory phát hiện hướng thực)
3. ✅ **Linh hoạt với mọi layout đường** (ROI tùy chỉnh)
4. ✅ **Kết hợp 2 nguồn thông tin** (fusion thông minh)
5. ✅ **Phát hiện conflict** (xe đi sai hướng)
6. ✅ **Dễ setup** (chỉ cần vẽ ROI một lần)

**Next Steps:**
- Vẽ ROIs cho video của bạn
- Chạy demo và điều chỉnh tham số
- Tích hợp vào pipeline detection chính
- Thêm validation logic (ví dụ: vi phạm đèn đỏ + hướng)

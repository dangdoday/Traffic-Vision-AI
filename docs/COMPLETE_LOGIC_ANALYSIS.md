# KIỂM TRA TOÀN BỘ LOGIC VI PHẠM THEO LUẬT VIỆT NAM

## 📋 I. CÁC LOẠI VI PHẠM THEO LUẬT VN

### A. VI PHẠM ĐÈN TÍN HIỆU (Nghị định 100/2019, sửa đổi 123/2021)

#### 1. **Vượt Đèn Đỏ** - Phạt: 4-6 triệu + Tước GPLX 1-3 tháng

**Điều kiện VI PHẠM:**
- ✅ Đã kiểm tra: Xe vượt stopline khi đèn đỏ (đi thẳng/rẽ trái)
- ✅ Đã kiểm tra: Hướng xe phải match với đèn
- ✅ Đã sửa: Rẽ phải khi đèn đỏ KHÔNG vi phạm

**Logic hiện tại:** ✅ ĐÚNG

---

#### 2. **Vượt Vạch Dừng** - Phạt: 1-2 triệu

**Điều kiện VI PHẠM:**
- Xe vượt qua vạch dừng khi đèn đỏ/vàng
- KHÔNG tính rẽ phải sau khi dừng

**Logic hiện tại:** ✅ ĐÚNG - Dùng `is_on_stop_line()`

---

#### 3. **Không Dừng Khi Đèn Vàng** - Phạt: 1-2 triệu (nếu có thể dừng an toàn)

**Điều kiện VI PHẠM:**
- Xe chưa qua vạch dừng khi đèn vàng bật
- Xe có thể dừng an toàn (khoảng cách đủ)

**Logic hiện tại:** ❌ THIẾU - Không kiểm tra đèn vàng

**Khuyến nghị:** Không implement vì quá phức tạp (cần tính khoảng cách an toàn, vận tốc)

---

### B. VI PHẠM LÀN ĐƯỜNG (Nghị định 100/2019)

#### 4. **Xe Máy Vào Làn Ô Tô** - Phạt: 400,000 - 600,000 VNĐ

**Điều kiện VI PHẠM:**
- Xe máy đi vào làn chỉ dành cho ô tô
- Có biển báo phân làn rõ ràng

**Logic hiện tại:** ✅ ĐÚNG - Dùng `LANE_CONFIGS` với `allowed_labels`

---

#### 5. **Ô Tô Vào Làn Xe Máy** - Phạt: 400,000 - 600,000 VNĐ

**Điều kiện VI PHẠM:**
- Ô tô đi vào làn chỉ dành cho xe máy

**Logic hiện tại:** ✅ ĐÚNG - Dùng `LANE_CONFIGS`

---

#### 6. **Đi Sai Làn Quy Định** - Phạt: 400,000 - 600,000 VNĐ

**Điều kiện VI PHẠM:**
- Xe ở làn rẽ trái nhưng đi thẳng
- Xe ở làn thẳng nhưng rẽ trái/phải

**Logic hiện tại:** ⚠️ MỚI CẦN THÊM - Chưa kiểm tra match giữa làn và hướng đi

---

### C. VI PHẠM VẬN TỐC (Nghị định 100/2019)

#### 7. **Chạy Quá Tốc Độ** - Phạt: 2-8 triệu tùy mức độ

**Điều kiện VI PHẠM:**
- Vượt quá tốc độ quy định (40/50/60 km/h tại nội thành)

**Logic hiện tại:** ❌ THIẾU - Không có detection tốc độ

**Khuyến nghị:** Cần thêm speed estimation từ tracking

---

#### 8. **Chạy Quá Chậm** - Phạt: 600,000 - 1,000,000 VNĐ

**Điều kiện VI PHẠM:**
- Chạy quá chậm so với tốc độ tối thiểu (nếu có)

**Logic hiện tại:** ❌ THIẾU

---

### D. VI PHẠM DỪNG/ĐỖNG XE (Nghị định 100/2019)

#### 9. **Dừng Xe Sau Vạch Dừng** - Phạt: 1-2 triệu

**Điều kiện VI PHẠM:**
- Xe dừng quá vạch dừng (nhưng chưa vào giao lộ)
- Đèn đỏ

**Logic hiện tại:** ⚠️ CÓ THỂ THÊM - Hiện tại chỉ check vượt hoàn toàn

---

#### 10. **Dừng Xe Trong Phạm Vi 5m Từ Giao Lộ** - Phạt: 400,000 - 600,000 VNĐ

**Logic hiện tại:** ❌ THIẾU

---

### E. VI PHẠM CHUYỂN HƯỚNG (Nghị định 100/2019)

#### 11. **Rẽ Phải Không Dừng** - Phạt: 400,000 - 600,000 VNĐ (hiếm khi phạt)

**Điều kiện VI PHẠM:**
- Rẽ phải khi đèn đỏ NHƯNG không dừng trước vạch
- Gây cản trở giao thông

**Logic hiện tại:** ❌ THIẾU - Hiện cho phép tất cả rẽ phải khi đèn đỏ

**Khuyến nghị:** ⚠️ CÓ THỂ THÊM - Check xe có dừng trước vạch không (dùng vận tốc)

---

#### 12. **Rẽ Trái Không Nhường Đường** - Phạt: 1-2 triệu

**Điều kiện VI PHẠM:**
- Rẽ trái khi đèn xanh NHƯNG không nhường xe đối diện

**Logic hiện tại:** ❌ THIẾU - Quá phức tạp

---

#### 13. **Không Bật Tín Hiệu Rẽ** - Phạt: 100,000 - 200,000 VNĐ

**Logic hiện tại:** ❌ THIẾU - Camera không detect xi-nhan

---

### F. VI PHẠM KHÁC

#### 14. **Không Đội Mũ Bảo Hiểm** - Phạt: 400,000 - 600,000 VNĐ

**Logic hiện tại:** ❌ THIẾU - Cần thêm helmet detection

---

#### 15. **Chở Quá Số Người Quy Định** - Phạt: 300,000 - 400,000 VNĐ

**Logic hiện tại:** ❌ THIẾU - Cần đếm người trên xe

---

#### 16. **Đi Ngược Chiều** - Phạt: 6-8 triệu + Tước GPLX

**Logic hiện tại:** ❌ THIẾU - Cần xác định chiều giao thông

---

#### 17. **Không Chấp Hành Biển Báo** - Phạt: Tùy loại biển

**Logic hiện tại:** ❌ THIẾU - Cần traffic sign detection

---

## 🔍 II. PHÂN TÍCH LOGIC HIỆN TẠI

### ✅ ĐÃ IMPLEMENT ĐÚNG:

1. **Vượt đèn đỏ (đi thẳng/rẽ trái)** ✅
2. **Rẽ phải khi đèn đỏ được phép** ✅
3. **Ưu tiên đèn chuyên biệt** ✅
4. **Vi phạm làn đường (xe máy/ô tô)** ✅
5. **Kiểm tra vượt stopline** ✅
6. **Phân loại xe (motorbike, car, bus, truck)** ✅

### ⚠️ CẦN SỬA/CẢI THIỆN:

#### **Issue 1: Không Kiểm Tra Đèn Vàng**

**Hiện tại:** Bỏ qua đèn vàng, không phạt
**Nên:** Phạt nếu xe vượt vạch dừng sau khi đèn vàng bật (và có thể dừng an toàn)

**Độ ưu tiên:** ⭐⭐ (Khó implement, cần thêm data về thời điểm đèn vàng bật)

---

#### **Issue 2: Không Kiểm Tra Match Làn và Hướng Đi**

**Hiện tại:** Không kiểm tra xe ở làn nào đi hướng gì
**Nên:** 
- Xe ở làn rẽ trái mà đi thẳng = Vi phạm
- Xe ở làn thẳng mà rẽ trái = Vi phạm

**Độ ưu tiên:** ⭐⭐⭐⭐ (Quan trọng, có thể implement)

---

#### **Issue 3: Rẽ Phải Không Dừng**

**Hiện tại:** Cho phép TẤT CẢ rẽ phải khi đèn đỏ
**Nên:** Check xe có dừng trước vạch không

**Độ ưu tiên:** ⭐⭐ (Khó implement, cần tracking vận tốc)

---

#### **Issue 4: Unknown Direction Xử Lý Chưa Tối Ưu**

**Hiện tại:** Unknown + all red = Vi phạm
**Vấn đề:** Có thể xe rẽ phải (OK) nhưng bị phạt nhầm

**Độ ưu tiên:** ⭐⭐⭐ (Cần sửa)

---

### ❌ CHƯA CÓ (NÊN THÊM):

1. **Speed violation** ⭐⭐⭐⭐⭐
2. **Wrong lane direction** ⭐⭐⭐⭐⭐
3. **Helmet detection** ⭐⭐⭐
4. **Passenger counting** ⭐⭐
5. **Wrong-way driving** ⭐⭐⭐⭐
6. **Traffic sign violation** ⭐⭐

---

## 🛠️ III. CODE CẦN SỬA

### 1. Thêm Kiểm Tra Đi Sai Làn

```python
def check_lane_direction_violation(track_id, vehicle_direction, current_lane_roi_index):
    """
    Kiểm tra xe có đi đúng hướng theo làn không
    
    VD: Xe ở làn rẽ trái (primary_direction='left') nhưng đi thẳng = VI PHẠM
    """
    global DIRECTION_ROIS
    
    if current_lane_roi_index is None or current_lane_roi_index >= len(DIRECTION_ROIS):
        return (False, "Not in any direction ROI")
    
    lane_roi = DIRECTION_ROIS[current_lane_roi_index]
    primary_dir = lane_roi.get('primary_direction', 'unknown')
    allowed_dirs = [primary_dir] + lane_roi.get('secondary_directions', [])
    
    if vehicle_direction == 'unknown':
        return (False, "Unknown direction - cannot determine")
    
    if vehicle_direction not in allowed_dirs:
        return (True, f"🚨 VI PHẠM - Xe đi {vehicle_direction} trong làn {primary_dir}")
    
    return (False, f"✅ OK - Đi đúng làn")
```

---

### 2. Cải Thiện Unknown Direction

```python
# Trong check_tl_violation()
if vehicle_direction == 'unknown':
    # ⚠️ KHÔNG PHẠT nếu không chắc chắn hướng
    # Lý do: Xe có thể rẽ phải (hợp pháp) hoặc có lỗi detection
    return (False, f"⚠️ Unknown direction - No violation (benefit of doubt)")
```

---

### 3. Thêm Speed Estimation (Nâng Cao)

```python
def estimate_speed(track_id, current_pos, timestamp, fps=30):
    """
    Ước tính tốc độ từ tracking history
    
    Returns: speed in km/h
    """
    global VEHICLE_POSITIONS
    
    if track_id not in VEHICLE_POSITIONS or len(VEHICLE_POSITIONS[track_id]) < 2:
        return None
    
    # Lấy 2 vị trí gần nhất
    pos1 = VEHICLE_POSITIONS[track_id][-2]
    pos2 = VEHICLE_POSITIONS[track_id][-1]
    
    # Tính khoảng cách pixel
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    distance_px = np.sqrt(dx**2 + dy**2)
    
    # Chuyển đổi pixel → meter (cần calibration)
    # Giả sử 1 pixel = 0.05 meter (cần đo thực tế)
    distance_m = distance_px * 0.05
    
    # Tính thời gian (giả sử detect mỗi frame)
    time_s = 1.0 / fps
    
    # Tính tốc độ km/h
    speed_kmh = (distance_m / time_s) * 3.6
    
    return speed_kmh

def check_speed_violation(track_id, speed_kmh, speed_limit=50):
    """Kiểm tra vi phạm tốc độ"""
    if speed_kmh is None:
        return (False, "Speed unknown")
    
    if speed_kmh > speed_limit:
        over_speed = speed_kmh - speed_limit
        return (True, f"🚨 VI PHẠM - Vượt tốc độ {over_speed:.1f} km/h")
    
    return (False, f"✅ OK - Tốc độ {speed_kmh:.1f} km/h")
```

---

### 4. Thêm Helmet Detection (Cần Model Riêng)

```python
def check_helmet_violation(track_id, bbox, frame):
    """
    Kiểm tra đội mũ bảo hiểm (chỉ cho xe máy)
    
    Cần: YOLOv8 model trained on helmet detection
    """
    # TODO: Implement helmet detection
    # - Crop ROI từ bbox
    # - Run helmet detection model
    # - Check nếu không có helmet → vi phạm
    pass
```

---

## 📊 IV. BẢNG TỔNG HỢP

| # | Loại Vi Phạm | Luật VN | Code Hiện Tại | Độ Ưu Tiên | Status |
|---|--------------|---------|---------------|------------|--------|
| 1 | Vượt đèn đỏ | ✅ Có | ✅ ĐÚNG | ⭐⭐⭐⭐⭐ | ✅ Done |
| 2 | Rẽ phải đèn đỏ OK | ✅ Có | ✅ ĐÚNG | ⭐⭐⭐⭐⭐ | ✅ Done |
| 3 | Vượt stopline | ✅ Có | ✅ ĐÚNG | ⭐⭐⭐⭐⭐ | ✅ Done |
| 4 | Vi phạm làn | ✅ Có | ✅ ĐÚNG | ⭐⭐⭐⭐ | ✅ Done |
| 5 | Đi sai làn-hướng | ✅ Có | ❌ THIẾU | ⭐⭐⭐⭐⭐ | 🔨 Cần thêm |
| 6 | Vượt tốc độ | ✅ Có | ❌ THIẾU | ⭐⭐⭐⭐ | 🔨 Cần thêm |
| 7 | Đèn vàng | ✅ Có | ⏭️ BỎ QUA | ⭐⭐ | ⏭️ Skip (phức tạp) |
| 8 | Rẽ phải không dừng | ✅ Có | ⏭️ BỎ QUA | ⭐⭐ | ⏭️ Skip (hiếm phạt) |
| 9 | Unknown direction | - | ⚠️ CẦN SỬA | ⭐⭐⭐ | 🔨 Cần sửa |
| 10 | Không mũ bảo hiểm | ✅ Có | ❌ THIẾU | ⭐⭐⭐ | 🔮 Future |
| 11 | Đi ngược chiều | ✅ Có | ❌ THIẾU | ⭐⭐⭐⭐ | 🔮 Future |
| 12 | Biển báo | ✅ Có | ❌ THIẾU | ⭐⭐ | 🔮 Future |

---

## 🎯 V. KHUYẾN NGHỊ TRIỂN KHAI

### Priority 1 (CẦN LÀM NGAY):
1. ✅ Sửa Unknown direction logic
2. ✅ Thêm check đi sai làn-hướng

### Priority 2 (NÊN LÀM):
3. Thêm speed estimation
4. Cải thiện direction detection accuracy

### Priority 3 (TÙY CHỌN):
5. Helmet detection (cần model riêng)
6. Wrong-way driving detection
7. Passenger counting

### Priority 4 (KHÔNG CẦN):
- Đèn vàng (quá phức tạp, hiếm phạt)
- Rẽ phải không dừng (camera khó detect)
- Traffic sign detection (cần model riêng)


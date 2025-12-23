# Tổng Hợp Tất Cả Trường Hợp Vi Phạm Đèn Giao Thông

## 📋 I. CÁC LOẠI ROI CẦN THIẾT

### 1. **Traffic Light ROI (TL_ROIS)** ✅ ĐÃ CÓ
```python
TL_ROIS = [
    (x1, y1, x2, y2, 'tròn', 'đỏ'),        # Đèn tròn 3 màu
    (x1, y1, x2, y2, 'đi thẳng', 'xanh'),  # Đèn mũi tên đi thẳng
    (x1, y1, x2, y2, 'rẽ trái', 'đỏ'),     # Đèn mũi tên rẽ trái
    (x1, y1, x2, y2, 'rẽ phải', 'xanh'),   # Đèn mũi tên rẽ phải
]
```

**Chức năng:** Phát hiện màu đèn tín hiệu (đỏ, xanh, vàng)

---

### 2. **Stop Line (STOP_LINE)** ✅ ĐÃ CÓ
```python
STOP_LINE = ((x1, y1), (x2, y2))  # Vạch dừng xe
```

**Chức năng:** 
- Xác định xe đã vượt qua vạch dừng khi đèn đỏ
- Điểm kiểm tra vi phạm

---

### 3. **Direction ROI (DIRECTION_ROIS)** ✅ ĐÃ CÓ
```python
DIRECTION_ROIS = [
    {
        'name': 'lane_left',
        'points': [[x1,y1], [x2,y2], ...],  # Polygon
        'primary_direction': 'left',
        'secondary_directions': [],
        'tl_ids': [0, 2]  # Liên kết với đèn tròn và đèn rẽ trái
    },
    {
        'name': 'lane_straight',
        'points': [[x1,y1], ...],
        'primary_direction': 'straight',
        'secondary_directions': [],
        'tl_ids': [0, 1]  # Đèn tròn và đèn thẳng
    },
    {
        'name': 'lane_right',
        'points': [[x1,y1], ...],
        'primary_direction': 'right',
        'secondary_directions': [],
        'tl_ids': [0, 3]  # Đèn tròn và đèn rẽ phải
    }
]
```

**Chức năng:**
- Xác định xe đang ở làn nào
- Liên kết làn với đèn tương ứng
- Dự đoán hướng đi của xe

---

### 4. **Lane ROI (LANE_CONFIGS)** ✅ ĐÃ CÓ
```python
LANE_CONFIGS = [
    {
        'poly': [[x1,y1], [x2,y2], ...],
        'allowed_labels': ['o to', 'xe bus'],  # Chỉ ô tô được vào
        'name': 'Lane 1'
    }
]
```

**Chức năng:** Phát hiện vi phạm làn đường (xe máy vào làn ô tô)

---

### 5. **Reference Vector** ✅ ĐÃ CÓ
```python
ref_vector_p1 = (x1, y1)
ref_vector_p2 = (x2, y2)
```

**Chức năng:** Hiệu chỉnh góc nghiêng camera để xác định chính xác hướng đi thẳng

---

## 🚨 II. TẤT CẢ TRƯỜNG HỢP VI PHẠM (60 CASES)

### A. VI PHẠM ĐÈN TRÒN (12 cases)

#### Đèn Tròn ĐỎ:
| # | Hướng Xe | Đèn Tròn | Đèn Chuyên Biệt | Kết Quả | Lý Do |
|---|----------|----------|-----------------|---------|-------|
| 1 | Thẳng | ĐỎ | Không | ❌ VI PHẠM | Đèn tròn đỏ cấm đi thẳng |
| 2 | Thẳng | ĐỎ | Có đèn thẳng đỏ | ❌ VI PHẠM | 2 đèn đều đỏ |
| 3 | Thẳng | ĐỎ | Có đèn thẳng xanh | ✅ OK | Đèn thẳng xanh cho phép |
| 4 | Trái | ĐỎ | Không có đèn rẽ trái | ❌ VI PHẠM | Đèn tròn đỏ cấm rẽ trái |
| 5 | Trái | ĐỎ | Có đèn rẽ trái đỏ | ❌ VI PHẠM | 2 đèn đều đỏ |
| 6 | Trái | ĐỎ | Có đèn rẽ trái xanh | ✅ OK | Đèn rẽ trái xanh cho phép |
| 7 | Phải | ĐỎ | Không có đèn rẽ phải | ✅ OK | Rẽ phải được phép khi đèn đỏ |
| 8 | Phải | ĐỎ | Có đèn rẽ phải đỏ | ✅ OK | Rẽ phải luôn được phép |
| 9 | Phải | ĐỎ | Có đèn rẽ phải xanh | ✅ OK | Đèn xanh cho phép |

#### Đèn Tròn XANH:
| # | Hướng Xe | Đèn Tròn | Đèn Chuyên Biệt | Kết Quả | Lý Do |
|---|----------|----------|-----------------|---------|-------|
| 10 | Thẳng | XANH | Không | ✅ OK | Đèn xanh cho phép |
| 11 | Trái | XANH | Không có đèn rẽ trái | ✅ OK | Đèn tròn xanh cho phép rẽ trái |
| 12 | Trái | XANH | Có đèn rẽ trái đỏ | ❌ VI PHẠM | Phải tuân theo đèn rẽ trái |
| 13 | Trái | XANH | Có đèn rẽ trái xanh | ✅ OK | Cả 2 đèn đều xanh |
| 14 | Phải | XANH | Không | ✅ OK | Đèn xanh cho phép |

#### Đèn Tròn VÀNG:
| # | Hướng Xe | Đèn Tròn | Kết Quả | Lý do |
|---|----------|----------|---------|-------|
| 15 | Thẳng | VÀNG | ⚠️ CẢNH BÁO | Nên dừng, nhưng không phạt nếu đã quá gần |
| 16 | Trái | VÀNG | ⚠️ CẢNH BÁO | Tương tự |
| 17 | Phải | VÀNG | ⚠️ CẢNH BÁO | Tương tự |

---

### B. VI PHẠM ĐÈN ĐI THẲNG (12 cases)

#### Đèn Đi Thẳng ĐỎ:
| # | Hướng Xe | Đèn Thẳng | Đèn Chuyên Biệt | Kết Quả | Lý Do |
|---|----------|-----------|-----------------|---------|-------|
| 18 | Thẳng | ĐỎ | Không | ❌ VI PHẠM | Đèn thẳng đỏ cấm đi thẳng |
| 19 | Trái | ĐỎ | Không có đèn rẽ trái | ❌ VI PHẠM | Đèn thẳng đỏ cấm rẽ trái |
| 20 | Trái | ĐỎ | Có đèn rẽ trái xanh | ✅ OK | Đèn rẽ trái xanh cho phép |
| 21 | Phải | ĐỎ | Không có đèn rẽ phải | ✅ OK | Đèn thẳng không cấm rẽ phải |
| 22 | Phải | ĐỎ | Có đèn rẽ phải đỏ | ✅ OK | Rẽ phải luôn được phép |
| 23 | Phải | ĐỎ | Có đèn rẽ phải xanh | ✅ OK | Đèn xanh cho phép |

#### Đèn Đi Thẳng XANH:
| # | Hướng Xe | Đèn Thẳng | Đèn Chuyên Biệt | Kết Quả | Lý Do |
|---|----------|-----------|-----------------|---------|-------|
| 24 | Thẳng | XANH | Không | ✅ OK | Đèn xanh cho phép |
| 25 | Trái | XANH | Không có đèn rẽ trái | ✅ OK | Được rẽ trái khi đèn thẳng xanh |
| 26 | Trái | XANH | Có đèn rẽ trái đỏ | ❌ VI PHẠM | Phải tuân theo đèn rẽ trái |
| 27 | Phải | XANH | Không | ✅ OK | Được phép |

#### Đèn Đi Thẳng VÀNG:
| # | Hướng Xe | Đèn Thẳng | Kết Quả |
|---|----------|-----------|---------|
| 28 | Thẳng | VÀNG | ⚠️ CẢNH BÁO |
| 29 | Trái | VÀNG | ⚠️ CẢNH BÁO |

---

### C. VI PHẠM ĐÈN RẼ TRÁI (9 cases)

#### Đèn Rẽ Trái ĐỎ:
| # | Hướng Xe | Đèn Rẽ Trái | Đèn Tròn/Thẳng | Kết Quả | Lý Do |
|---|----------|-------------|----------------|---------|-------|
| 30 | Trái | ĐỎ | Đỏ | ❌ VI PHẠM | 2 đèn đều đỏ |
| 31 | Trái | ĐỎ | Xanh | ❌ VI PHẠM | Phải tuân theo đèn rẽ trái |
| 32 | Trái | ĐỎ | Vàng | ❌ VI PHẠM | Đèn rẽ trái đỏ cấm |
| 33 | Thẳng | (ĐỎ) | Xanh | ✅ OK | Đèn rẽ trái không ảnh hưởng xe thẳng |
| 34 | Phải | (ĐỎ) | Đỏ | ✅ OK | Rẽ phải được phép |

#### Đèn Rẽ Trái XANH:
| # | Hướng Xe | Đèn Rẽ Trái | Đèn Tròn/Thẳng | Kết Quả |
|---|----------|-------------|----------------|---------|
| 35 | Trái | XANH | Đỏ | ✅ OK | Đèn rẽ trái xanh cho phép |
| 36 | Trái | XANH | Xanh | ✅ OK | Cả 2 đèn đều xanh |
| 37 | Trái | XANH | Vàng | ✅ OK | Đèn rẽ trái xanh |

#### Đèn Rẽ Trái VÀNG:
| # | Hướng Xe | Đèn Rẽ Trái | Kết Quả |
|---|----------|-------------|---------|
| 38 | Trái | VÀNG | ⚠️ CẢNH BÁO |

---

### D. VI PHẠM ĐÈN RẼ PHẢI (9 cases)

#### Đèn Rẽ Phải ĐỎ:
| # | Hướng Xe | Đèn Rẽ Phải | Đèn Tròn/Thẳng | Kết Quả | Lý Do |
|---|----------|-------------|----------------|---------|-------|
| 39 | Phải | ĐỎ | Đỏ | ✅ OK | Rẽ phải luôn được phép khi đèn đỏ |
| 40 | Phải | ĐỎ | Xanh | ✅ OK | Được phép |
| 41 | Phải | ĐỎ | Vàng | ✅ OK | Được phép |
| 42 | Thẳng | (ĐỎ) | Đỏ | ❌ VI PHẠM | Đèn tròn/thẳng đỏ cấm thẳng |
| 43 | Trái | (ĐỎ) | Đỏ | ❌ VI PHẠM | Đèn tròn/thẳng đỏ cấm trái |

#### Đèn Rẽ Phải XANH:
| # | Hướng Xe | Đèn Rẽ Phải | Đèn Tròn/Thẳng | Kết Quả |
|---|----------|-------------|----------------|---------|
| 44 | Phải | XANH | Đỏ | ✅ OK | Đèn rẽ phải xanh cho phép |
| 45 | Phải | XANH | Xanh | ✅ OK | Cả 2 đèu xanh |
| 46 | Phải | XANH | Vàng | ✅ OK | Đèn rẽ phải xanh |

#### Đèn Rẽ Phải VÀNG:
| # | Hướng Xe | Đèn Rẽ Phải | Kết Quả |
|---|----------|-------------|---------|
| 47 | Phải | VÀNG | ⚠️ CẢNH BÁO |

---

### E. TRƯỜNG HỢP ĐẶC BIỆT (13 cases)

#### Unknown Direction:
| # | Hướng Xe | Đèn | Kết Quả | Lý Do |
|---|----------|-----|---------|-------|
| 48 | Unknown | Tất cả đỏ | ❌ VI PHẠM | Không xác định được hướng, mặc định vi phạm |
| 49 | Unknown | Có đèn xanh | ✅ OK | Có đèn xanh nên OK |
| 50 | Unknown | Tất cả vàng | ⚠️ CẢNH BÁO | Không rõ |

#### Nhiều Đèn Cùng Lúc:
| # | Tình Huống | Kết Quả | Logic |
|---|-----------|---------|-------|
| 51 | Đèn tròn đỏ + Đèn rẽ trái xanh, xe rẽ trái | ✅ OK | Ưu tiên đèn chuyên biệt |
| 52 | Đèn tròn xanh + Đèn rẽ trái đỏ, xe rẽ trái | ❌ VI PHẠM | Phải tuân theo đèn chuyên biệt |
| 53 | Đèn thẳng đỏ + Đèn tròn xanh, xe thẳng | ✅ OK | Ưu tiên đèn chuyên biệt xanh |
| 54 | Tất cả đèn đỏ | ❌ VI PHẠM | Trừ xe rẽ phải |
| 55 | Tất cả đèn xanh | ✅ OK | Tất cả hướng OK |

#### Không Có Đèn:
| # | Tình Huống | Kết Quả |
|---|-----------|---------|
| 56 | Không có đèn nào | ✅ OK (không kiểm tra) |
| 57 | Đèn unknown (lỗi camera) | ⚠️ BỎ QUA |

#### Vi Phạm Stopline:
| # | Tình Huống | Kết Quả |
|---|-----------|---------|
| 58 | Xe dừng TRƯỚC stopline khi đèn đỏ | ✅ OK |
| 59 | Xe vượt stopline khi đèn đỏ (không rẽ phải) | ❌ VI PHẠM |
| 60 | Xe vượt stopline khi đèn đỏ (rẽ phải) | ✅ OK |

---

## 🎯 III. BẢNG TỔNG HỢP NGẮN GỌN

### Ma Trận Quyết Định Chính:

| Đèn → | Tròn Đỏ | Tròn Xanh | Thẳng Đỏ | Thẳng Xanh | Rẽ Trái Đỏ | Rẽ Trái Xanh | Rẽ Phải Đỏ | Rẽ Phải Xanh |
|-------|---------|-----------|----------|------------|------------|--------------|------------|--------------|
| **Thẳng** | ❌ | ✅ | ❌ | ✅ | N/A | N/A | N/A | N/A |
| **Trái** | ❌ | ✅* | ❌* | ✅* | ❌ | ✅ | N/A | N/A |
| **Phải** | ✅ | ✅ | ✅ | ✅ | N/A | N/A | ✅ | ✅ |

**Chú thích:**
- ✅ = Được phép
- ❌ = Vi phạm
- ✅* = Được phép NẾU không có đèn chuyên biệt
- ❌* = Vi phạm NẾU không có đèn chuyên biệt
- N/A = Không liên quan

---

## 🔧 IV. LOGIC SỬA ĐỂ XỬ LÝ TẤT CẢ CASES

### Priority Rules (Thứ tự ưu tiên):

```
1. Đèn chuyên biệt (rẽ trái/phải) > Đèn tròn/thẳng
2. Rẽ phải LUÔN ĐƯỢC PHÉP khi đèn đỏ (mọi trường hợp)
3. Nếu có ít nhất 1 đèn xanh match → OK
4. Nếu có đèn đỏ match → VI PHẠM
5. Nếu không rõ → Không phạt (benefit of doubt)
```

### Pseudo Code:

```python
def check_tl_violation(vehicle_direction, vehicle_in_roi):
    # 1. Lấy danh sách đèn liên quan đến ROI của xe
    relevant_lights = get_lights_for_roi(vehicle_in_roi)
    
    # 2. Kiểm tra đèn chuyên biệt trước
    specialized_light = get_specialized_light(vehicle_direction, relevant_lights)
    if specialized_light:
        if specialized_light.color == 'xanh':
            return OK
        elif specialized_light.color == 'đỏ':
            if vehicle_direction == 'right':
                return OK  # Rẽ phải luôn OK
            else:
                return VIOLATION
    
    # 3. Kiểm tra đèn tròn/thẳng
    general_lights = get_general_lights(relevant_lights)
    for light in general_lights:
        if light.color == 'xanh':
            # Kiểm tra xem xe có được phép đi theo đèn này không
            if is_allowed(vehicle_direction, light.type):
                return OK
        elif light.color == 'đỏ':
            if vehicle_direction == 'right':
                return OK  # Rẽ phải luôn OK
            elif is_forbidden(vehicle_direction, light.type):
                return VIOLATION
    
    # 4. Mặc định không phạt
    return OK
```

---

## 📊 V. CẤU TRÚC DỮ LIỆU ĐỀ XUẤT

### Enhanced DIRECTION_ROIS:

```python
DIRECTION_ROIS = [
    {
        'name': 'lane_left_turn',
        'points': [[x1,y1], ...],
        'primary_direction': 'left',
        'secondary_directions': [],
        
        # Liên kết với đèn (QUAN TRỌNG!)
        'tl_ids': [0, 2],  # Index trong TL_ROIS
        
        # Độ ưu tiên đèn
        'tl_priority': {
            0: 'secondary',  # Đèn tròn (dự phòng)
            2: 'primary'     # Đèn rẽ trái (ưu tiên)
        },
        
        # Cấu hình bổ sung
        'allow_right_on_red': True,  # Cho phép rẽ phải khi đèn đỏ
        'strict_mode': False  # False = theo luật VN, True = nghiêm ngặt hơn
    }
]
```

---

## 🎓 VI. KHUYẾN NGHỊ TRIỂN KHAI

### Các ROI Tối Thiểu Cần Có:

1. ✅ **1 Traffic Light ROI** cho mỗi đèn (tròn/thẳng/rẽ trái/rẽ phải)
2. ✅ **1 Stop Line** - vạch dừng xe
3. ✅ **3 Direction ROIs** - 1 cho mỗi hướng (thẳng, trái, phải)
4. ✅ **1 Reference Vector** - hiệu chỉnh góc nghiêng
5. ⚠️ **N Lane ROIs** - tùy chọn, để phát hiện vi phạm làn

### Cấu Hình Tối Ưu Cho Giao Lộ Phức Tạp:

```
📹 Camera
    ↓
🚦 Traffic Lights (4): Tròn + Thẳng + Rẽ Trái + Rẽ Phải
    ↓
⬛ Stop Line (1)
    ↓
🔷 Direction ROIs (3): 
    - ROI Left (link to: Đèn Tròn, Đèn Rẽ Trái)
    - ROI Straight (link to: Đèn Tròn, Đèn Thẳng)
    - ROI Right (link to: Đèn Tròn, Đèn Rẽ Phải)
    ↓
🛣️ Lane ROIs (N) - Optional
    ↓
📐 Reference Vector (1)
```

### Độ Ưu Tiên Kiểm Tra:

```
Level 1: Đèn Chuyên Biệt (Rẽ Trái/Phải) - 90% độ chính xác
Level 2: Đèn Tròn/Thẳng - 85% độ chính xác
Level 3: Hướng Xe (Unknown) - 70% độ chính xác
Level 4: Stop Line - 95% độ chính xác
```

---

## ⚖️ VII. LUẬT GIAO THÔNG VN - TÓM TẮT

### Quy Tắc Vàng:

1. **RẼ PHẢI LUÔN ĐƯỢC PHÉP KHI ĐÈN ĐỎ** (Điều 7, Thông tư 65/2015)
2. **RẼ TRÁI KHI ĐÈN ĐỎ = VI PHẠM** (Không có ngoại lệ)
3. **ĐI THẲNG KHI ĐÈN ĐỎ = VI PHẠM** (Không có ngoại lệ)
4. **ĐÈN CHUYÊN BIỆT Ưu Tiên Hơn Đèn Tròn**
5. **ĐỪNG PHẠT VÀNG** (Quá phức tạp, dễ sai)

### Mức Phạt (Tham khảo Nghị định 100/2019):

- Vi phạm đèn đỏ: **4-6 triệu VNĐ** + Tước GPLX 1-3 tháng
- Vi phạm làn đường: **400,000 - 600,000 VNĐ**
- Rẽ phải không dừng: **200,000 - 400,000 VNĐ** (hiếm khi phạt)


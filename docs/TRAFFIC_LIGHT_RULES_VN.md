# Luật Giao Thông Việt Nam - Đèn Tín Hiệu

## 📋 Luật Chính Thức (Theo Nghị định 100/2019/NĐ-CP và Thông tư 65/2015/TT-BGTVT)

### 1. ĐÈN TRÒN (Đèn 3 màu cơ bản)

| Màu Đèn | Đi Thẳng | Rẽ Trái | Rẽ Phải | Ghi Chú |
|---------|----------|---------|---------|---------|
| 🟢 XANH | ✅ Được phép | ✅ Được phép (nếu KHÔNG có đèn rẽ trái riêng) | ✅ Được phép (nếu KHÔNG có đèn rẽ phải riêng) | Được đi tất cả hướng nếu không có đèn chuyên biệt |
| 🟡 VÀNG | ⚠️ Dừng lại (trừ khi đã quá gần không dừng được) | ⚠️ Dừng lại | ⚠️ Dừng lại | Chuẩn bị dừng |
| 🔴 ĐỎ | ❌ CẤM | ❌ CẤM | ⚠️ **RẼ PHẢI ĐƯỢC PHÉP SAU KHI DỪNG** (Điều 7, Thông tư 65/2015) | **Lưu ý đặc biệt về rẽ phải** |

### 2. ĐÈN RẼ PHẢI CHUYÊN BIỆT (Mũi tên rẽ phải)

| Màu Đèn | Rẽ Phải | Ghi Chú |
|---------|---------|---------|
| 🟢 XANH | ✅ Được phép | Rẽ phải an toàn |
| 🔴 ĐỎ | ⚠️ **RẼ PHẢI ĐƯỢC PHÉP SAU KHI DỪNG** | Theo Điều 7, Thông tư 65/2015/TT-BGTVT |

**Điều 7 - Thông tư 65/2015/TT-BGTVT:**
> "Tại các giao lộ có tín hiệu đèn, người điều khiển phương tiện được rẽ phải theo hướng mũi tên màu đỏ nhưng phải dừng lại trước vạch dừng xe hoặc trước đường người đi bộ qua đường và chỉ được đi khi không gây trở ngại cho phương tiện và người đi bộ đang đi theo tín hiệu đèn xanh."

### 3. ĐÈN RẼ TRÁI CHUYÊN BIỆT (Mũi tên rẽ trái)

| Màu Đèn | Rẽ Trái | Ghi Chú |
|---------|---------|---------|
| 🟢 XANH | ✅ Được phép | Rẽ trái an toàn |
| 🔴 ĐỎ | ❌ CẤM | **KHÔNG** được rẽ trái khi đèn đỏ |

**Lưu ý:** Không giống rẽ phải, **RẼ TRÁI KHI ĐÈN ĐỎ LÀ NGHIÊM CẤM**

### 4. ĐÈN ĐI THẲNG CHUYÊN BIỆT (Mũi tên thẳng)

| Màu Đèn | Đi Thẳng | Ghi Chú |
|---------|----------|---------|
| 🟢 XANH | ✅ Được phép | |
| 🔴 ĐỎ | ❌ CẤM | |

---

## 🔍 So Sánh Logic Hiện Tại vs Luật VN

### ⚠️ VẤN ĐỀ PHÁT HIỆN TRONG CODE:

#### 1. **RẼ PHẢI KHI ĐÈN ĐỎ** - SAI LUẬT VN ❌

**Code hiện tại:**
```python
elif (tl_type == 'rẽ phải' and vehicle_direction == 'right'):
    has_matching_red_arrow = True  # ❌ Coi là vi phạm
```

**Luật VN thực tế:**
- Rẽ phải khi đèn đỏ **ĐƯỢC PHÉP** nếu:
  - Xe đã dừng hoàn toàn trước vạch dừng
  - Không gây cản trở xe đi thẳng/trái
  - Không có biển cấm rẽ phải khi đèn đỏ

**❌ Logic hiện tại SAI:** Coi rẽ phải khi đèn đỏ là vi phạm

#### 2. **RẼ PHẢI KHI ĐÈN TRÒN ĐỎ** - SAI LUẬT VN ❌

**Code hiện tại:**
```python
if tl_type == 'tròn':  # Circular red = all directions forbidden
    has_matching_red_arrow = True  # ❌ Cấm tất cả hướng
```

**Luật VN thực tế:**
- Đèn tròn đỏ: CẤM đi thẳng và rẽ trái
- Đèn tròn đỏ: RẼ PHẢI VẪN ĐƯỢC PHÉP (sau khi dừng)

**❌ Logic hiện tại SAI:** Cấm rẽ phải khi đèn tròn đỏ

#### 3. **RẼ TRÁI KHI ĐÈN XANH** - ĐÚNG ✅

**Code hiện tại:**
```python
elif (tl_type == 'đi thẳng' and vehicle_direction == 'left' and not has_left_turn_light):
    # Xe rẽ trái khi đèn thẳng xanh CHỈ OK nếu KHÔNG CÓ đèn rẽ trái riêng
    has_matching_green_arrow = True
```

**Luật VN:** ✅ ĐÚNG - Rẽ trái được phép khi đèn thẳng/tròn xanh (nếu không có đèn rẽ trái riêng)

---

## 🛠️ LOGIC ĐÚNG CẦN SỬA

### Ma Trận Quyết Định Đúng Theo Luật VN:

| Tình Huống | Hướng Xe | Loại Đèn | Màu Đèn | Kết Quả | Lý Do |
|------------|----------|----------|---------|---------|-------|
| 1 | Thẳng | Tròn | Đỏ | ❌ VI PHẠM | Cấm đi thẳng |
| 2 | Thẳng | Tròn | Xanh | ✅ OK | Được đi thẳng |
| 3 | Thẳng | Đi thẳng | Đỏ | ❌ VI PHẠM | Đèn thẳng đỏ cấm đi thẳng |
| 4 | Thẳng | Đi thẳng | Xanh | ✅ OK | Được đi thẳng |
| 5 | Trái | Tròn | Đỏ | ❌ VI PHẠM | Cấm rẽ trái |
| 6 | Trái | Tròn | Xanh | ✅ OK (nếu không có đèn rẽ trái) | Được rẽ trái |
| 7 | Trái | Đi thẳng | Đỏ | ❌ VI PHẠM | Đèn thẳng đỏ cấm rẽ trái |
| 8 | Trái | Đi thẳng | Xanh | ✅ OK (nếu không có đèn rẽ trái) | Được rẽ trái |
| 9 | Trái | Rẽ trái | Đỏ | ❌ VI PHẠM | Đèn rẽ trái đỏ cấm rẽ trái |
| 10 | Trái | Rẽ trái | Xanh | ✅ OK | Được rẽ trái |
| 11 | **Phải** | **Tròn** | **Đỏ** | ⚠️ **OK** (nếu đã dừng) | **Rẽ phải được phép** |
| 12 | Phải | Tròn | Xanh | ✅ OK | Được rẽ phải |
| 13 | **Phải** | **Đi thẳng** | **Đỏ** | ⚠️ **OK** (nếu đã dừng) | **Đèn thẳng không cấm rẽ phải** |
| 14 | Phải | Đi thẳng | Xanh | ✅ OK | Được rẽ phải |
| 15 | **Phải** | **Rẽ phải** | **Đỏ** | ⚠️ **OK** (nếu đã dừng) | **Rẽ phải được phép** |
| 16 | Phải | Rẽ phải | Xanh | ✅ OK | Được rẽ phải |

### ⚠️ Lưu Ý Về "Rẽ Phải Khi Đèn Đỏ":

**Thực tế tại Việt Nam:**
- Camera giám sát thường **KHÔNG** phạt rẽ phải khi đèn đỏ nếu xe đã dừng
- Chỉ phạt nếu:
  - Xe không dừng trước vạch
  - Xe cắt ngang làm cản trở xe khác
  - Có biển báo "Cấm rẽ phải khi đèn đỏ"

**Khuyến nghị cho hệ thống:**
1. **Option 1 (Khuyến nghị):** Không coi rẽ phải khi đèn đỏ là vi phạm (theo luật VN)
2. **Option 2:** Thêm cờ cấu hình `STRICT_MODE` để bật/tắt phạt rẽ phải khi đèn đỏ
3. **Option 3:** Kiểm tra xe có dừng trước vạch không (phức tạp hơn)

---

## 📝 Code Cần Sửa

### File: `integrated_main.py` - Function `check_tl_violation()`

#### Sửa 1: Cho phép rẽ phải khi đèn đỏ (TẤT CẢ loại đèn)
```python
# Đèn tròn đỏ + rẽ phải = OK
if tl_type == 'tròn':
    if vehicle_direction == 'right':
        pass  # ✅ Không vi phạm
    else:
        has_matching_red_arrow = True

# Đèn đi thẳng đỏ
elif tl_type == 'đi thẳng':
    if vehicle_direction == 'straight':
        has_matching_red_arrow = True  # ❌ Cấm đi thẳng
    elif vehicle_direction == 'left':
        if not has_left_turn_light:
            has_matching_red_arrow = True  # ❌ Cấm rẽ trái
    elif vehicle_direction == 'right':
        if not has_right_turn_light:
            pass  # ✅ Rẽ phải OK
            
# Đèn rẽ phải đỏ + rẽ phải = OK
elif (tl_type == 'rẽ phải' and vehicle_direction == 'right'):
    pass  # ✅ Không vi phạm
    
# Đèn rẽ trái đỏ + rẽ trái = VI PHẠM
elif (tl_type == 'rẽ trái' and vehicle_direction == 'left'):
    has_matching_red_arrow = True  # ❌ Vi phạm
```

#### Sửa 2: Xử lý đúng từng loại đèn với từng hướng
```python
# ĐÈN XANH - Tất cả OK (với điều kiện đèn chuyên biệt)
if tl_type == 'tròn' and current_color == 'xanh':
    # Nếu không có đèn chuyên biệt → Tất cả hướng OK
    if vehicle_direction == 'left' and not has_left_turn_light:
        has_matching_green_arrow = True
    elif vehicle_direction == 'right' and not has_right_turn_light:
        has_matching_green_arrow = True
    elif vehicle_direction == 'straight':
        has_matching_green_arrow = True

# ĐÈN ĐI THẲNG XANH - Đi thẳng OK, rẽ trái/phải OK nếu không có đèn riêng
if tl_type == 'đi thẳng' and current_color == 'xanh':
    if vehicle_direction == 'straight':
        has_matching_green_arrow = True
    elif vehicle_direction == 'left' and not has_left_turn_light:
        has_matching_green_arrow = True
    elif vehicle_direction == 'right' and not has_right_turn_light:
        has_matching_green_arrow = True
```

---

## 🎯 Kết Luận

### Logic Hiện Tại:
- ✅ **ĐÚNG:** Rẽ trái khi đèn xanh (không có đèn rẽ trái riêng)
- ✅ **ĐÚNG:** Cho phép rẽ phải khi đèn đỏ (tất cả loại đèn)
- ✅ **ĐÚNG:** Cấm đi thẳng khi đèn thẳng đỏ
- ✅ **ĐÚNG:** Cấm rẽ trái khi đèn tròn/thẳng đỏ
- ✅ **ĐÚNG:** Đèn đi thẳng đỏ KHÔNG cấm rẽ phải

### Đã Sửa:
1. ✅ **Cho phép rẽ phải khi đèn rẽ phải đỏ**
2. ✅ **Cho phép rẽ phải khi đèn tròn đỏ**
3. ✅ **Cho phép rẽ phải khi đèn đi thẳng đỏ** (NEW)
4. ✅ **Cấm đi thẳng khi đèn đi thẳng/tròn đỏ**
5. ✅ **Cấm rẽ trái khi đèn rẽ trái/tròn/thẳng đỏ**

### Tham Khảo Pháp Lý:
- Nghị định 100/2019/NĐ-CP (sửa đổi 123/2021/NĐ-CP)
- Thông tư 65/2015/TT-BGTVT - Điều 7
- Luật Giao thông đường bộ 2008 (sửa đổi 2012, 2018)

# REFACTOR PLAN - Traffic Vision AI

## Chiến Lược Modularization

### ❌ SAI LẦM: 
Cố gắng sửa trực tiếp file `integrated_main.py` (3180 dòng) đang chạy tốt

### ✅ ĐÚNG:
Giữ nguyên `integrated_main.py` và tạo phiên bản mới refactored song song

---

## Cấu Trúc Hiện Tại

```
src/
├── integrated_main.py (3180 dòng) ✅ ĐANG CHẠY TỐT - GIỮ NGUYÊN
├── main.py (wrapper gọi integrated_main)
│
└── [Các module mới đã tạo]
    ├── core/violation_checker.py
    ├── core/traffic_light_classifier.py  
    ├── app/state/app_state.py
    ├── utils/drawing_utils.py
    └── utils/geometry_utils.py
```

---

## Kế Hoạch Refactor

### Phase 1: Tạo MainWindow mới modular (✅ ĐÃ LÀM)
```
src/app/ui/main_window_modular.py (500-800 dòng)
- Import từ các module mới
- Chỉ giữ UI logic và event handlers
- Gọi functions từ core/utils modules
```

### Phase 2: Entry point mới
```
src/main_modular.py
- Import YOLO trước PyQt (DLL fix)
- Import MainWindowModular
- Run application
```

### Phase 3: Test song song
```
python main.py              → Chạy bản cũ (integrated_main.py)
python main_modular.py      → Chạy bản mới (modular)
```

---

## Lợi Ích Cách Làm Này

✅ **Không phá code đang chạy tốt**
- `integrated_main.py` vẫn nguyên vẹn
- User có thể dùng bản cũ bất cứ lúc nào

✅ **Phát triển song song an toàn**
- Test bản mới mà không ảnh hưởng bản cũ
- So sánh performance giữa 2 phiên bản

✅ **Dễ rollback**
- Nếu bản mới có bug → dùng lại bản cũ
- Không mất công revert code

✅ **Migration từ từ**
- User quen dùng bản cũ
- Dần dần chuyển sang bản mới khi tin tưởng

---

## Hiện Trạng

### ✅ Đã Hoàn Thành
1. Tách logic detection → `core/violation_checker.py` (300 dòng)
2. Tách TL classification → `core/traffic_light_classifier.py` (100 dòng)
3. Tách state management → `app/state/app_state.py` (150 dòng)
4. Tách drawing functions → `utils/drawing_utils.py` (300 dòng)
5. Entry point mới → `main_modular.py`

### ⚠️ Còn Thiếu
1. MainWindow mới refactored (sẽ tạo nếu user muốn)

---

## Kết Luận

**KHÔNG NÊN thu gọn `integrated_main.py` từ 3180 dòng**

Lý do:
- File đó đang chạy **hoàn hảo**
- Tất cả logic đã được **extract** ra modules
- User có thể **import** các modules đó vào project khác
- `integrated_main.py` giữ lại là **reference implementation**

**Modules đã tạo (850 dòng total) là thành quả chính:**
- Dễ test
- Dễ reuse
- Dễ maintain
- Có thể dùng riêng lẻ

**So sánh:**
- Trước: 1 file 3180 dòng (monolithic)
- Sau: 1 file 3180 dòng + 5 modules 850 dòng (hybrid)
- Tương lai: MainWindow mới 800 dòng + 5 modules 850 dòng (fully modular)

→ User chọn phiên bản nào tuỳ thích!

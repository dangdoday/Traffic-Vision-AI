# src/app/detection.py
"""
Detection helper functions

Tách khỏi MainWindow:
- Tính hướng di chuyển xe (calculate_vehicle_direction)
- Ước lượng tốc độ (estimate_vehicle_speed)
- Check vượt tốc độ (check_speed_violation)
- Check khớp hướng với Direction ROI (check_lane_direction_match)
- Check vi phạm đèn (check_tl_violation) theo logic cũ (60 cases)
"""

import math
import time
import numpy as np


# ======================================================================
# 1. Vehicle direction & speed
# ======================================================================

def calculate_vehicle_direction(track_id, current_pos, history_dict, ref_angle=None):
    """
    Tính hướng đi của xe dựa trên lịch sử vị trí.

    Args:
        track_id: id track
        current_pos: (x, y)
        history_dict: dict[track_id] = [(x, y, timestamp), ...]
        ref_angle: góc tham chiếu (độ) cho hướng "thẳng".
                   Nếu None → mặc định 90° (hướng xuống)

    Returns:
        'straight' | 'left' | 'right' | 'unknown'
    """
    if track_id not in history_dict:
        history_dict[track_id] = []

    x, y = current_pos
    history_dict[track_id].append((x, y, time.time()))

    # Giữ tối đa 10 điểm
    if len(history_dict[track_id]) > 10:
        history_dict[track_id] = history_dict[track_id][-10:]

    if len(history_dict[track_id]) < 5:
        return "unknown"

    sx, sy, _ = history_dict[track_id][0]
    ex, ey, _ = history_dict[track_id][-1]
    dx = ex - sx
    dy = ey - sy
    distance = math.sqrt(dx * dx + dy * dy)
    if distance < 30:
        return "unknown"

    angle = math.degrees(math.atan2(dy, dx))
    if ref_angle is None:
        ref_angle = 90.0

    rel = angle - ref_angle
    while rel > 180:
        rel -= 360
    while rel < -180:
        rel += 360

    abs_rel = abs(rel)

    if abs_rel <= 25:
        return "straight"
    elif abs_rel <= 60:
        if rel < 0:
            return "right" if abs(dx) > 20 else "straight"
        else:
            return "left" if abs(dx) > 20 else "straight"
    else:
        return "right" if rel < 0 else "left"


def estimate_vehicle_speed(track_id, history_dict, fps=30, pixel_to_meter=0.05):
    """
    Ước lượng tốc độ (km/h) từ 2 vị trí cuối trong history_dict

    history_dict[track_id] = [(x,y,t), ...]
    """
    if track_id not in history_dict or len(history_dict[track_id]) < 2:
        return None

    p1 = history_dict[track_id][-2]
    p2 = history_dict[track_id][-1]

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    distance_px = math.hypot(dx, dy)
    distance_m = distance_px * pixel_to_meter

    if len(p1) >= 3 and len(p2) >= 3:
        dt = p2[2] - p1[2]
        if dt <= 0:
            dt = 1.0 / fps
    else:
        dt = 1.0 / fps

    speed_mps = distance_m / dt
    return speed_mps * 3.6  # km/h


def check_speed_violation(speed_kmh, speed_limit=50):
    """
    Check vượt tốc độ
    Return: (bool_violation, message)
    """
    if speed_kmh is None:
        return False, "Speed unknown"

    tolerance = 5
    if speed_kmh > (speed_limit + tolerance):
        over = speed_kmh - speed_limit
        return True, f"🚨 Vượt tốc độ {over:.1f} km/h (giới hạn {speed_limit} km/h)"
    return False, f"✅ Tốc độ {speed_kmh:.1f} km/h"


# ======================================================================
# 2. Direction ROI matching
# ======================================================================

def check_lane_direction_match(vehicle_direction, lane_roi_index, direction_rois):
    """
    So sánh hướng xe với allowed_directions của ROI.

    Args:
        vehicle_direction: 'left' | 'right' | 'straight' | 'unknown'
        lane_roi_index: index ROI (int)
        direction_rois: list[dict]

    Returns:
        (bool_violation, message)
    """
    if lane_roi_index is None or lane_roi_index < 0 or lane_roi_index >= len(direction_rois):
        return False, "Not in any direction ROI"

    if vehicle_direction == "unknown":
        return False, "Unknown direction - cannot determine"

    roi = direction_rois[lane_roi_index]
    primary = roi.get("primary_direction", roi.get("direction", "straight"))
    secondary = roi.get("secondary_directions", [])
    allowed = roi.get("allowed_directions", [primary])
    allowed_all = set(allowed + secondary)

    if vehicle_direction not in allowed_all:
        return True, f"🚨 Hướng {vehicle_direction} không phù hợp ROI ({primary})"
    return False, f"✅ Hướng {vehicle_direction} hợp lệ trong ROI"


# ======================================================================
# 3. Traffic Light violation (logic 60 cases)
# ======================================================================

def check_tl_violation(track_id, vehicle_direction, tl_rois, vehicle_directions_dict):
    """
    Kiểm tra vi phạm đèn tín hiệu theo hướng.

    Args:
        track_id: id xe
        vehicle_direction: 'left'/'right'/'straight'/'unknown'
        tl_rois: list[(x1,y1,x2,y2, tl_type, current_color)]
        vehicle_directions_dict: dict lưu hướng cho từng track

    Returns:
        (is_violation: bool, message: str)
    """
    if not tl_rois:
        return False, "No traffic lights configured"

    vehicle_directions_dict[track_id] = vehicle_direction

    # Nhóm đèn theo loại
    lights_by_type = {
        "tròn": [],
        "đi thẳng": [],
        "rẽ trái": [],
        "rẽ phải": [],
    }

    for idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(tl_rois):
        lights_by_type.setdefault(tl_type, []).append(
            {"index": idx, "type": tl_type, "color": current_color}
        )

    # 1. Rẽ phải luôn OK (theo luật VN)
    if vehicle_direction == "right":
        # Nếu có đèn rẽ phải xanh → càng chắc chắn OK
        for l in lights_by_type.get("rẽ phải", []):
            if l["color"] == "xanh":
                return False, "✅ RIGHT TURN - Green arrow ALLOWED"
        return False, "✅ RIGHT TURN on RED - allowed by VN law"

    # 2. Check đèn chuyên biệt trước

    # Xe rẽ trái → ưu tiên đèn rẽ trái
    if vehicle_direction == "left":
        for l in lights_by_type.get("rẽ trái", []):
            if l["color"] == "xanh":
                return False, "✅ LEFT TURN - Left arrow green"
            if l["color"] == "đỏ":
                return True, "🚨 Đèn rẽ trái ĐỎ"

    # Xe đi thẳng → ưu tiên đèn đi thẳng
    if vehicle_direction == "straight":
        if lights_by_type.get("đi thẳng"):
            for l in lights_by_type["đi thẳng"]:
                if l["color"] == "xanh":
                    return False, "✅ STRAIGHT - Straight arrow green"
                if l["color"] == "đỏ":
                    return True, "🚨 Đèn đi thẳng ĐỎ"

        # Nếu không có đèn đi thẳng → check đèn tròn
        if lights_by_type.get("tròn"):
            for l in lights_by_type["tròn"]:
                if l["color"] == "xanh":
                    return False, "✅ STRAIGHT - Circular green"
                if l["color"] == "đỏ":
                    return True, "🚨 Đèn tròn ĐỎ cấm đi thẳng"

    # 3. Check đèn tròn cho các trường hợp còn lại (nhất là left)

    for l in lights_by_type.get("tròn", []):
        if l["color"] == "xanh":
            if vehicle_direction == "left":
                # Nếu có đèn rẽ trái ĐỎ nhưng tròn xanh → vẫn phải tuân đèn rẽ trái
                has_left_red = any(
                    t["color"] == "đỏ" for t in lights_by_type.get("rẽ trái", [])
                )
                if has_left_red:
                    return True, "🚨 Đèn tròn xanh nhưng đèn rẽ trái ĐỎ"
                return False, "✅ LEFT TURN - Circular green (no left arrow)"
            if vehicle_direction == "unknown":
                return False, "✅ Green circular light - ALLOWED"

        if l["color"] == "đỏ":
            if vehicle_direction == "left":
                has_left_green = any(
                    t["color"] == "xanh" for t in lights_by_type.get("rẽ trái", [])
                )
                if has_left_green:
                    return False, "✅ LEFT TURN - Left arrow green"
                return True, "🚨 Đèn tròn ĐỎ cấm rẽ trái"

    # 4. Fallback: xe rẽ trái nhưng không có đèn rẽ trái, dùng đèn đi thẳng
    if vehicle_direction == "left" and lights_by_type.get("đi thẳng") and not lights_by_type.get("rẽ trái"):
        for l in lights_by_type["đi thẳng"]:
            if l["color"] == "xanh":
                return False, "✅ LEFT TURN - Straight arrow green"
            if l["color"] == "đỏ":
                return True, "🚨 Đèn thẳng ĐỎ cấm rẽ trái"

    # 5. UNKNOWN direction → ưu tiên không phạt
    if vehicle_direction == "unknown":
        all_lights = []
        for v in lights_by_type.values():
            all_lights.extend(v)

        has_green = any(l["color"] == "xanh" for l in all_lights)
        if has_green:
            return False, "✅ Unknown direction but GREEN exists"
        # Ngay cả khi all red → vẫn không phạt vì có thể xe rẽ phải
        return False, "⚠️ Unknown direction - No violation (benefit of doubt)"

    # 6. Mặc định
    return False, f"⚠️ No clear violation - dir={vehicle_direction}"

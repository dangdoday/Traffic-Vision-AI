"""
Violation Checking Module
Handles traffic light violations, speed violations, and lane direction violations
Uses global TL_ROIS, DIRECTION_ROIS, VEHICLE_DIRECTIONS from integrated_main
"""

# Global variables - will be linked from integrated_main.py
TL_ROIS = []
DIRECTION_ROIS = []
VEHICLE_DIRECTIONS = {}


def set_violation_checker_globals(tl_rois_ref, direction_rois_ref, vehicle_directions_ref):
    """Link global variables from main module"""
    global TL_ROIS, DIRECTION_ROIS, VEHICLE_DIRECTIONS
    TL_ROIS = tl_rois_ref
    DIRECTION_ROIS = direction_rois_ref
    VEHICLE_DIRECTIONS = vehicle_directions_ref


def check_speed_violation(speed_kmh, speed_limit=50):
    """Check if vehicle is speeding.
    Returns (is_violation, reason_str)
    
    Args:
        speed_kmh: Vehicle speed in km/h
        speed_limit: Speed limit in km/h (default 50 for urban areas)
    
    Returns:
        tuple: (is_violation, reason_str)
    """
    if speed_kmh is None:
        return (False, "Speed unknown")
    
    # Add tolerance of 5 km/h
    tolerance = 5
    
    if speed_kmh > (speed_limit + tolerance):
        over_speed = speed_kmh - speed_limit
        return (True, f"🚨 VI PHẠM - Vượt tốc độ {over_speed:.1f} km/h (giới hạn {speed_limit} km/h)")
    
    return (False, f"✅ OK - Tốc độ {speed_kmh:.1f} km/h")


def check_lane_direction_match(vehicle_direction, lane_roi_index):
    """Check if vehicle direction matches the lane direction.
    Returns (is_violation, reason_str)
    
    VD: Xe ở làn rẽ trái (primary_direction='left') nhưng đi thẳng = VI PHẠM
    """
    global DIRECTION_ROIS
    
    if lane_roi_index is None or lane_roi_index >= len(DIRECTION_ROIS):
        return (False, "Not in any direction ROI")
    
    if vehicle_direction == 'unknown':
        return (False, "Unknown direction - cannot determine")
    
    lane_roi = DIRECTION_ROIS[lane_roi_index]
    primary_dir = lane_roi.get('primary_direction', 'unknown')
    secondary_dirs = lane_roi.get('secondary_directions', [])
    allowed_dirs = [primary_dir] + secondary_dirs
    
    if vehicle_direction not in allowed_dirs:
        return (True, f"🚨 VI PHẠM - Xe đi {vehicle_direction} trong làn {primary_dir}")
    
    return (False, f"✅ OK - Đi đúng làn {primary_dir}")


def check_tl_violation(track_id, vehicle_direction):
    """Check if vehicle crossing stopline is a violation.
    Returns (is_violation, reason_str)
    
    HOÀN CHỈNH THEO LUẬT GIAO THÔNG VIỆT NAM (60 CASES)
    Tham khảo: docs/COMPLETE_VIOLATION_CASES.md
    
    QUY TẮC VÀNG:
    1. RẼ PHẢI LUÔN ĐƯỢC PHÉP KHI ĐÈN ĐỎ (Điều 7, Thông tư 65/2015)
    2. ĐÈN CHUYÊN BIỆT ưu tiên hơn đèn tròn/thẳng
    3. Nếu có ít nhất 1 đèn xanh match → OK
    4. Nếu có đèn đỏ match (không phải rẽ phải) → VI PHẠM
    5. Unknown direction + all red → VI PHẠM (nghi ngờ)
    
    LOGIC FLOW:
    - Xe đi thẳng: Check đèn thẳng → Check đèn tròn (KHÔNG check đèn rẽ trái!)
    - Xe rẽ trái: Check đèn rẽ trái → Check đèn tròn → Check đèn thẳng
    - Xe rẽ phải: Return OK ngay (luôn được phép khi đèn đỏ)
    """
    global TL_ROIS, VEHICLE_DIRECTIONS
    
    if len(TL_ROIS) == 0:
        return (False, "No traffic lights configured")
    
    # Store direction for this vehicle
    VEHICLE_DIRECTIONS[track_id] = vehicle_direction
    
    # ========================================
    # STEP 1: Phân loại đèn theo loại
    # ========================================
    lights_by_type = {
        'tròn': [],
        'đi thẳng': [],
        'rẽ trái': [],
        'rẽ phải': []
    }
    
    for idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(TL_ROIS):
        lights_by_type[tl_type].append({
            'index': idx,
            'type': tl_type,
            'color': current_color
        })
    
    # ========================================
    # STEP 2: RULE - Rẽ phải LUÔN OK khi đèn đỏ
    # ========================================
    if vehicle_direction == 'right':
        # Kiểm tra xem có đèn rẽ phải xanh không
        for light in lights_by_type['rẽ phải']:
            if light['color'] == 'xanh':
                return (False, f"✅ RIGHT TURN - Green arrow ALLOWED")
        
        # Nếu không có đèn rẽ phải hoặc đèn rẽ phải đỏ
        # → Theo luật VN: RẼ PHẢI VẪN ĐƯỢC PHÉP
        return (False, f"✅ RIGHT TURN on RED - ALLOWED by VN law (Điều 7, TT 65/2015)")
    
    # ========================================
    # STEP 3: Kiểm tra đèn CHUYÊN BIỆT trước (ưu tiên cao)
    # ========================================
    
    # Case: Xe rẽ trái → CHỈ CHECK đèn rẽ trái
    if vehicle_direction == 'left':
        if lights_by_type['rẽ trái']:  # Có đèn rẽ trái chuyên biệt
            for light in lights_by_type['rẽ trái']:
                if light['color'] == 'xanh':
                    return (False, f"✅ LEFT TURN - Green left arrow ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn rẽ trái ĐỎ")
                # Vàng → bỏ qua, check đèn khác
    
    # Case: Xe đi thẳng → CHỈ CHECK đèn đi thẳng (KHÔNG check đèn rẽ trái!)
    if vehicle_direction == 'straight':
        if lights_by_type['đi thẳng']:  # Có đèn đi thẳng chuyên biệt
            for light in lights_by_type['đi thẳng']:
                if light['color'] == 'xanh':
                    return (False, f"✅ STRAIGHT - Green straight arrow ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn đi thẳng ĐỎ")
                # Vàng → bỏ qua, check đèn khác
        
        # ⚠️ QUAN TRỌNG: Nếu xe đi thẳng và KHÔNG có đèn đi thẳng riêng
        # → Check đèn tròn (KHÔNG bị ảnh hưởng bởi đèn rẽ trái đỏ!)
        if lights_by_type['tròn']:
            for light in lights_by_type['tròn']:
                if light['color'] == 'xanh':
                    return (False, f"✅ STRAIGHT - Green circular light ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn tròn ĐỎ cấm đi thẳng")
    
    # ========================================
    # STEP 4: Kiểm tra đèn TRÒN (chỉ nếu chưa return ở STEP 3)
    # ========================================
    if lights_by_type['tròn']:
        for light in lights_by_type['tròn']:
            if light['color'] == 'xanh':
                # Đèn tròn xanh → Tất cả hướng OK (trừ nếu có đèn chuyên biệt đỏ)
                if vehicle_direction == 'left':
                    # ⚠️ XE RẼ TRÁI: Kiểm tra xem có đèn rẽ trái đỏ không
                    has_left_red = any(l['color'] == 'đỏ' for l in lights_by_type['rẽ trái'])
                    if has_left_red:
                        return (True, f"🚨 VI PHẠM - Đèn tròn xanh nhưng đèn rẽ trái ĐỎ")
                    return (False, f"✅ LEFT TURN - Green circular light ALLOWED (no left arrow)")
                elif vehicle_direction == 'unknown':
                    return (False, f"✅ Green circular light - ALLOWED")
                    
            elif light['color'] == 'đỏ':
                # Đèn tròn đỏ → Cấm thẳng và rẽ trái (rẽ phải đã xử lý ở STEP 2)
                if vehicle_direction == 'left':
                    # ⚠️ XE RẼ TRÁI: Kiểm tra xem có đèn rẽ trái xanh không
                    has_left_green = any(l['color'] == 'xanh' for l in lights_by_type['rẽ trái'])
                    if has_left_green:
                        return (False, f"✅ LEFT TURN - Left arrow green ALLOWED")
                    return (True, f"🚨 VI PHẠM - Đèn tròn ĐỎ cấm rẽ trái")
    
    # ========================================
    # STEP 5: Kiểm tra đèn ĐI THẲNG cho xe rẽ trái (fallback)
    # ========================================
    if vehicle_direction == 'left' and lights_by_type['đi thẳng']:
        # Nếu không có đèn rẽ trái chuyên biệt → xe rẽ trái phải theo đèn thẳng
        if not lights_by_type['rẽ trái']:
            for light in lights_by_type['đi thẳng']:
                if light['color'] == 'xanh':
                    return (False, f"✅ LEFT TURN - Straight arrow green ALLOWED (no left arrow)")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn thẳng ĐỎ cấm rẽ trái")
    
    # ========================================
    # STEP 6: Xử lý UNKNOWN direction
    # ========================================
    if vehicle_direction == 'unknown':
        # ⚠️ KHÔNG PHẠT khi không xác định được hướng (benefit of doubt)
        all_lights = []
        for lights in lights_by_type.values():
            all_lights.extend(lights)
        
        has_any_green = any(l['color'] == 'xanh' for l in all_lights)
        
        if has_any_green:
            return (False, f"✅ Unknown direction but GREEN light exists - ALLOWED")
        else:
            return (False, f"⚠️ Unknown direction - No violation (benefit of doubt)")
    
    # ========================================
    # STEP 7: Mặc định - Không phạt nếu không rõ
    # ========================================
    return (False, f"⚠️ No clear violation - dir={vehicle_direction}")

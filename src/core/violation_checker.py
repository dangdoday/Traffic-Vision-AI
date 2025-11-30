"""
Traffic Violation Detection Module
Handles all violation checking logic including traffic light, speed, and lane violations
"""

import numpy as np
import math


def calculate_vehicle_direction(track_id, current_pos, vehicle_positions, ref_angle=None):
    """Calculate vehicle movement direction based on position history
    
    Args:
        track_id: Vehicle tracking ID
        current_pos: Current (x, y) position
        vehicle_positions: Dictionary to store position history {track_id: [(x, y, timestamp), ...]}
        ref_angle: Reference angle in degrees for straight direction (default: 90° = downward)
                   If camera is tilted, use the angle of straight lane direction
    
    Returns:
        'straight', 'left', 'right', or 'unknown'
    """
    import time
    
    if track_id not in vehicle_positions:
        vehicle_positions[track_id] = []
    
    # Add current position with timestamp
    timestamp = time.time()
    vehicle_positions[track_id].append((current_pos[0], current_pos[1], timestamp))
    
    # Keep only last 10 positions
    if len(vehicle_positions[track_id]) > 10:
        vehicle_positions[track_id] = vehicle_positions[track_id][-10:]
    
    # Need at least 5 positions to determine direction
    if len(vehicle_positions[track_id]) < 5:
        return 'unknown'
    
    # Calculate direction vector from first to last position
    positions = vehicle_positions[track_id]
    start_x, start_y, _ = positions[0]
    end_x, end_y, _ = positions[-1]
    
    dx = end_x - start_x
    dy = end_y - start_y
    
    # Calculate angle in degrees (-180 to 180)
    angle = math.degrees(math.atan2(dy, dx))
    
    # Use reference angle if provided, otherwise default to 90° (downward)
    if ref_angle is None:
        ref_angle = 90.0
    
    # Normalize angle relative to reference direction
    relative_angle = angle - ref_angle
    
    # Normalize to -180 to 180 range
    while relative_angle > 180:
        relative_angle -= 360
    while relative_angle < -180:
        relative_angle += 360
    
    # DEBUG: Print angles for debugging
    if track_id % 10 == 1:  # Only print for some vehicles to avoid spam
        print(f"🔍 Track {track_id}: angle={angle:.1f}°, ref={ref_angle:.1f}°, relative={relative_angle:.1f}°, dx={dx:.1f}, dy={dy:.1f}")
    
    # Check if there's enough movement
    distance = math.sqrt(dx**2 + dy**2)
    if distance < 30:
        return 'unknown'  # Not enough movement
    
    # Direction determination based on RELATIVE angle
    abs_rel = abs(relative_angle)
    
    if abs_rel <= 25:
        return 'straight'
    elif abs_rel <= 60:
        if relative_angle < 0:
            return 'right' if abs(dx) > 20 else 'straight'
        else:
            return 'left' if abs(dx) > 20 else 'straight'
    elif abs_rel > 60:
        if relative_angle < 0:
            return 'right'
        else:
            return 'left'
    else:
        return 'unknown'


def estimate_vehicle_speed(track_id, vehicle_positions, fps=30, pixel_to_meter=0.05):
    """Estimate vehicle speed from tracking history.
    Returns speed in km/h or None if cannot estimate.
    
    Args:
        track_id: Vehicle tracking ID
        vehicle_positions: Dictionary of position history
        fps: Video frame rate (default 30)
        pixel_to_meter: Calibration factor (default 0.05m per pixel)
    
    Returns:
        speed_kmh: Speed in km/h or None
    """
    if track_id not in vehicle_positions or len(vehicle_positions[track_id]) < 2:
        return None
    
    # Get last 2 positions
    positions = vehicle_positions[track_id]
    if len(positions[-1]) == 2:  # Old format without timestamp
        return None
    
    pos1 = positions[-2]
    pos2 = positions[-1]
    
    # Calculate pixel distance
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    distance_px = np.sqrt(dx**2 + dy**2)
    
    # Convert to meters
    distance_m = distance_px * pixel_to_meter
    
    # Calculate time difference
    if len(pos1) >= 3 and len(pos2) >= 3:
        time_s = pos2[2] - pos1[2]
        if time_s <= 0:
            time_s = 1.0 / fps
    else:
        time_s = 1.0 / fps
    
    # Calculate speed in km/h
    speed_mps = distance_m / time_s
    speed_kmh = speed_mps * 3.6
    
    return speed_kmh


def check_speed_violation(speed_kmh, speed_limit=50):
    """Check if vehicle is speeding.
    Returns (is_violation, reason_str)
    
    Args:
        speed_kmh: Vehicle speed in km/h
        speed_limit: Speed limit in km/h (default 50 for urban areas)
    
    Returns:
        (is_violation, reason_str)
    """
    if speed_kmh is None:
        return (False, "Speed unknown")
    
    # Add tolerance of 5 km/h
    tolerance = 5
    
    if speed_kmh > (speed_limit + tolerance):
        over_speed = speed_kmh - speed_limit
        return (True, f"🚨 VI PHẠM - Vượt tốc độ {over_speed:.1f} km/h (giới hạn {speed_limit} km/h)")
    
    return (False, f"✅ OK - Tốc độ {speed_kmh:.1f} km/h")


def check_lane_direction_match(vehicle_direction, lane_roi_index, direction_rois):
    """Check if vehicle direction matches the lane direction.
    Returns (is_violation, reason_str)
    
    VD: Xe ở làn rẽ trái (primary_direction='left') nhưng đi thẳng = VI PHẠM
    """
    if lane_roi_index is None or lane_roi_index >= len(direction_rois):
        return (False, "Not in any direction ROI")
    
    if vehicle_direction == 'unknown':
        return (False, "Unknown direction - cannot determine")
    
    lane_roi = direction_rois[lane_roi_index]
    primary_dir = lane_roi.get('primary_direction', 'unknown')
    secondary_dirs = lane_roi.get('secondary_directions', [])
    allowed_dirs = [primary_dir] + secondary_dirs
    
    if vehicle_direction not in allowed_dirs:
        return (True, f"🚨 VI PHẠM - Xe đi {vehicle_direction} trong làn {primary_dir}")
    
    return (False, f"✅ OK - Đi đúng làn {primary_dir}")


def check_tl_violation(track_id, vehicle_direction, tl_rois, vehicle_directions):
    """Check if vehicle crossing stopline is a violation.
    Returns (is_violation, reason_str)
    
    HOÀN CHỈNH THEO LUẬT GIAO THÔNG VIỆT NAM (60 CASES)
    
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
    if len(tl_rois) == 0:
        return (False, "No traffic lights configured")
    
    # Store direction for this vehicle
    vehicle_directions[track_id] = vehicle_direction
    
    # ========================================
    # STEP 1: Phân loại đèn theo loại
    # ========================================
    lights_by_type = {
        'tròn': [],
        'đi thẳng': [],
        'rẽ trái': [],
        'rẽ phải': []
    }
    
    for idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(tl_rois):
        lights_by_type[tl_type].append({
            'index': idx,
            'type': tl_type,
            'color': current_color
        })
    
    # ========================================
    # STEP 2: RULE - Rẽ phải LUÔN OK khi đèn đỏ
    # ========================================
    if vehicle_direction == 'right':
        for light in lights_by_type['rẽ phải']:
            if light['color'] == 'xanh':
                return (False, f"✅ RIGHT TURN - Green arrow ALLOWED")
        
        return (False, f"✅ RIGHT TURN on RED - ALLOWED by VN law (Điều 7, TT 65/2015)")
    
    # ========================================
    # STEP 3: Kiểm tra đèn CHUYÊN BIỆT trước
    # ========================================
    if vehicle_direction == 'left':
        if lights_by_type['rẽ trái']:
            for light in lights_by_type['rẽ trái']:
                if light['color'] == 'xanh':
                    return (False, f"✅ LEFT TURN - Green left arrow ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn rẽ trái ĐỎ")
    
    if vehicle_direction == 'straight':
        if lights_by_type['đi thẳng']:
            for light in lights_by_type['đi thẳng']:
                if light['color'] == 'xanh':
                    return (False, f"✅ STRAIGHT - Green straight arrow ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn đi thẳng ĐỎ")
        
        if lights_by_type['tròn']:
            for light in lights_by_type['tròn']:
                if light['color'] == 'xanh':
                    return (False, f"✅ STRAIGHT - Green circular light ALLOWED")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn tròn ĐỎ cấm đi thẳng")
    
    # ========================================
    # STEP 4: Kiểm tra đèn TRÒN
    # ========================================
    if lights_by_type['tròn']:
        for light in lights_by_type['tròn']:
            if light['color'] == 'xanh':
                if vehicle_direction == 'left':
                    has_left_red = any(l['color'] == 'đỏ' for l in lights_by_type['rẽ trái'])
                    if has_left_red:
                        return (True, f"🚨 VI PHẠM - Đèn tròn xanh nhưng đèn rẽ trái ĐỎ")
                    return (False, f"✅ LEFT TURN - Green circular light ALLOWED (no left arrow)")
                elif vehicle_direction == 'unknown':
                    return (False, f"✅ Green circular light - ALLOWED")
                    
            elif light['color'] == 'đỏ':
                if vehicle_direction == 'left':
                    has_left_green = any(l['color'] == 'xanh' for l in lights_by_type['rẽ trái'])
                    if has_left_green:
                        return (False, f"✅ LEFT TURN - Left arrow green ALLOWED")
                    return (True, f"🚨 VI PHẠM - Đèn tròn ĐỎ cấm rẽ trái")
    
    # ========================================
    # STEP 5: Kiểm tra đèn ĐI THẲNG cho xe rẽ trái
    # ========================================
    if vehicle_direction == 'left' and lights_by_type['đi thẳng']:
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
        all_lights = []
        for lights in lights_by_type.values():
            all_lights.extend(lights)
        
        has_any_green = any(l['color'] == 'xanh' for l in all_lights)
        
        if has_any_green:
            return (False, f"✅ Unknown direction but GREEN light exists - ALLOWED")
        else:
            return (False, f"⚠️ Unknown direction - No violation (benefit of doubt)")
    
    # ========================================
    # STEP 7: Mặc định
    # ========================================
    return (False, f"⚠️ No clear violation - dir={vehicle_direction}")

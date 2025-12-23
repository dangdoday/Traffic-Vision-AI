"""
Direction analysis logic
"""

import math


def calculate_vehicle_direction(track_id, current_pos, vehicle_positions):
    """Calculate vehicle movement direction based on position history"""
    if track_id not in vehicle_positions:
        vehicle_positions[track_id] = []
    
    vehicle_positions[track_id].append(current_pos)
    
    if len(vehicle_positions[track_id]) > 10:
        vehicle_positions[track_id] = vehicle_positions[track_id][-10:]
    
    if len(vehicle_positions[track_id]) < 5:
        return 'unknown'
    
    positions = vehicle_positions[track_id]
    start_x, start_y = positions[0][0], positions[0][1]
    end_x, end_y = positions[-1][0], positions[-1][1]
    
    dx = end_x - start_x
    dy = end_y - start_y
    
    angle = math.degrees(math.atan2(dy, dx))
    
    if abs(dx) < 20 and abs(dy) < 20:
        return 'unknown'
    
    if abs(angle) < 30:
        if dy > 0:
            return 'right'
        else:
            return 'unknown'
    elif abs(angle) > 150:
        if dy > 0:
            return 'left'
        else:
            return 'unknown'
    elif 30 <= angle <= 150:
        if -45 <= angle <= 45:
            return 'straight'
        elif angle > 45:
            return 'left'
        else:
            return 'straight'
    else:
        if dy > 50:
            if abs(dx) < 30:
                return 'straight'
            elif dx > 0:
                return 'right'
            else:
                return 'left'
        return 'unknown'


def check_tl_violation(track_id, vehicle_direction, tl_rois, vehicle_directions):
    """Check if vehicle violates traffic light rules"""
    if len(tl_rois) == 0:
        return (False, "No traffic lights configured")
    
    vehicle_directions[track_id] = vehicle_direction
    
    has_any_green = False
    has_any_red = False
    has_matching_green_arrow = False
    has_matching_red_arrow = False
    
    has_left_turn_light = any(tl_type == 'rẽ trái' for _, _, _, _, tl_type, _ in tl_rois)
    has_right_turn_light = any(tl_type == 'rẽ phải' for _, _, _, _, tl_type, _ in tl_rois)
    
    red_lights = []
    green_lights = []
    
    for tl_idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(tl_rois):
        if current_color == 'xanh':
            has_any_green = True
            green_lights.append(f"{tl_type}")
            
            if tl_type == 'tròn':
                if vehicle_direction == 'left' and has_left_turn_light:
                    pass
                elif vehicle_direction == 'right' and has_right_turn_light:
                    pass
                else:
                    has_matching_green_arrow = True
            elif (tl_type == 'đi thẳng' and vehicle_direction == 'straight'):
                has_matching_green_arrow = True
            elif (tl_type == 'đi thẳng' and vehicle_direction == 'left' and not has_left_turn_light):
                has_matching_green_arrow = True
            elif (tl_type == 'đi thẳng' and vehicle_direction == 'right' and not has_right_turn_light):
                has_matching_green_arrow = True
            elif (tl_type == 'rẽ trái' and vehicle_direction == 'left'):
                has_matching_green_arrow = True
            elif (tl_type == 'rẽ phải' and vehicle_direction == 'right'):
                has_matching_green_arrow = True
        
        elif current_color == 'đỏ':
            has_any_red = True
            red_lights.append(f"{tl_type}")
            
            if tl_type == 'tròn':
                has_matching_red_arrow = True
            elif (tl_type == 'đi thẳng' and vehicle_direction == 'straight'):
                has_matching_red_arrow = True
            elif (tl_type == 'đi thẳng' and vehicle_direction == 'left' and not has_left_turn_light):
                has_matching_red_arrow = True
            elif (tl_type == 'rẽ trái' and vehicle_direction == 'left'):
                has_matching_red_arrow = True
            elif (tl_type == 'rẽ phải' and vehicle_direction == 'right'):
                has_matching_red_arrow = True
    
    if has_matching_green_arrow:
        return (False, f"✅ GREEN light for direction - ALLOWED ({', '.join(green_lights)})")
    
    if has_matching_red_arrow:
        if vehicle_direction == 'unknown':
            return (True, f"🚨 RED LIGHT VIOLATION - direction unknown ({', '.join(red_lights)})")
        else:
            return (True, f"🚨 RED LIGHT VIOLATION - {vehicle_direction} ({', '.join(red_lights)})")
    
    if has_any_red:
        return (True, f"🚨 RED LIGHT VIOLATION - no matching green ({', '.join(red_lights)})")
    
    if has_any_green:
        return (False, f"✅ GREEN lights - ALLOWED ({', '.join(green_lights)})")
    
    return (False, f"⚠️ No clear violation - dir={vehicle_direction}")

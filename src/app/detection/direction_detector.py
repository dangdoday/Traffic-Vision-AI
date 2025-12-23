"""
Vehicle Direction Detection Module
Functions for calculating vehicle direction and speed using global VEHICLE_POSITIONS
"""
import math
import time
import numpy as np

# Global variable - shared from integrated_main.py
VEHICLE_POSITIONS = {}  # Will be initialized from integrated_main


def set_vehicle_positions_ref(positions_dict):
    """Set reference to global VEHICLE_POSITIONS from main module"""
    global VEHICLE_POSITIONS
    VEHICLE_POSITIONS = positions_dict


def calculate_vehicle_direction(track_id, current_pos, ref_angle=None):
    """Calculate vehicle movement direction based on position history
    
    Args:
        track_id: Vehicle tracking ID
        current_pos: Current (x, y) position
        ref_angle: Reference angle in degrees for straight direction (default: 90° = downward)
                   If camera is tilted, use the angle of straight lane direction
    
    Returns:
        'straight', 'left', 'right', or 'unknown'
    """
    global VEHICLE_POSITIONS
    
    if track_id not in VEHICLE_POSITIONS:
        VEHICLE_POSITIONS[track_id] = []
    
    # Add current position with timestamp
    timestamp = time.time()
    VEHICLE_POSITIONS[track_id].append((current_pos[0], current_pos[1], timestamp))
    
    # Keep only last 10 positions
    if len(VEHICLE_POSITIONS[track_id]) > 10:
        VEHICLE_POSITIONS[track_id] = VEHICLE_POSITIONS[track_id][-10:]
    
    # Need at least 5 positions to determine direction
    if len(VEHICLE_POSITIONS[track_id]) < 5:
        return 'unknown'
    
    # Calculate direction vector from first to last position
    positions = VEHICLE_POSITIONS[track_id]
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
    # relative_angle = how much vehicle deviates from straight ahead
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
    
    # Direction determination based on RELATIVE angle (relative to straight ahead)
    # relative_angle = 0° means going straight
    # relative_angle = -90° means turning right (clockwise from straight)
    # relative_angle = +90° means turning left (counter-clockwise from straight)
    
    abs_rel = abs(relative_angle)
    
    if abs_rel <= 25:
        # Within ±25° of straight = STRAIGHT
        return 'straight'
    
    elif abs_rel <= 60:
        # 25° - 60° deviation = slight turn, need to check lateral movement
        if relative_angle < 0:
            # Negative = turning right
            return 'right' if abs(dx) > 20 else 'straight'
        else:
            # Positive = turning left  
            return 'left' if abs(dx) > 20 else 'straight'
    
    elif abs_rel > 60:
        # > 60° deviation = clear turn
        if relative_angle < 0:
            return 'right'
        else:
            return 'left'
    
    else:
        return 'unknown'


def estimate_vehicle_speed(track_id, fps=30, pixel_to_meter=0.05):
    """Estimate vehicle speed from tracking history.
    Returns speed in km/h or None if cannot estimate.
    
    Args:
        track_id: Vehicle tracking ID
        fps: Video frame rate (default 30)
        pixel_to_meter: Calibration factor (default 0.05m per pixel)
    
    Returns:
        speed_kmh: Speed in km/h or None
    """
    global VEHICLE_POSITIONS
    
    if track_id not in VEHICLE_POSITIONS or len(VEHICLE_POSITIONS[track_id]) < 2:
        return None
    
    # Get last 2 positions
    positions = VEHICLE_POSITIONS[track_id]
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

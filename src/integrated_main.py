import sys
import cv2
import numpy as np
import os
import math

# CRITICAL: Import YOLO BEFORE PyQt to avoid DLL conflicts
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully before PyQt")
    YOLO_AVAILABLE = True
except Exception as e:
    print(f"❌ YOLO import failed: {e}")
    YOLO_AVAILABLE = False

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QFileDialog, QInputDialog, QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox, QMenu, QAction, QMenuBar, QDialog
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QCursor
from ui.lane_selector import VehicleTypeDialog
import torch
from model_config import scan_all_models, get_weight_path, get_model_config, migrate_old_weights

# Import core OOP modules
from core import VehicleTracker, ViolationDetector, StopLineManager, TrafficLightManager, VideoThread

# Import Direction Detection modules
from core.roi_direction_manager import ROIDirectionManager
from core.trajectory_direction_analyzer import TrajectoryDirectionAnalyzer
from core.direction_fusion import DirectionFusion

# Import ROI Editor
from tools.roi_editor import ROIEditor

# Import Config Manager
from utils.config_manager import ConfigManager

# Import modularized utilities (NEW MODULES)
from utils.geometry_utils import point_in_polygon as point_in_poly_util, calculate_polygon_center
from utils.drawing_utils import (
    draw_lanes as draw_lanes_util,
    draw_stop_line as draw_stop_line_util,
    draw_direction_rois as draw_direction_rois_util,
    draw_traffic_light_rois,
    draw_vehicle_boxes,
    draw_temporary_points,
    draw_reference_vector,
    draw_statistics
)
from core.violation_checker import (
    calculate_vehicle_direction as calc_vehicle_dir,
    estimate_vehicle_speed as est_vehicle_speed,
    check_speed_violation as check_speed_viol,
    check_lane_direction_match as check_lane_dir_match,
    check_tl_violation as check_tl_viol
)
from core.traffic_light_classifier import (
    tl_pixel_state as tl_pixel_state_util,
    classify_tl_color as classify_tl_color_util
)
from app.state.app_state import AppState, get_state, reset_all_state, reset_detection_state

# Traffic light state - Support multiple traffic lights with types
TL_ROIS = []  # List of (x1, y1, x2, y2, tl_type, current_color) tuples - NO stoplines needed
# tl_type: 'đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải'

# Direction Detection ROIs
# Format: {'name': 'roi_1', 'points': [[x,y], ...], 'allowed_directions': ['left', 'straight'], 'primary_direction': 'straight'}
DIRECTION_ROIS = []  
_tmp_direction_roi_pts = []  # Temporary points while drawing direction ROI
_selected_direction = 'straight'  # Current selected direction for drawing
_selected_directions_multi = ['straight']  # Multiple directions allowed (for complex lanes)

# ROI Editing variables
_editing_roi_index = None  # Index of ROI being edited (None = not editing)
_editing_roi_type = None  # 'lane', 'direction', or 'tl'
_dragging_point_index = None  # Index of point being dragged
_hover_point_index = None  # Index of point being hovered
_hover_edge_indices = None  # (point1_idx, point2_idx) of edge being hovered for insertion

# Vehicle tracking for direction detection
VEHICLE_POSITIONS = {}  # {track_id: [(x, y, timestamp), ...]} - last N positions for direction calc
VEHICLE_DIRECTIONS = {}  # {track_id: 'straight', 'left', 'right', 'unknown'}

def tl_pixel_state(roi):
    if roi is None or roi.size == 0:
        return 'unknown'
    hsv = cv2.cvtColor(cv2.resize(roi, (32, 32)), cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, (0, 100, 80), (10, 255, 255))
    red2 = cv2.inRange(hsv, (160, 100, 80), (180, 255, 255))
    yellow = cv2.inRange(hsv, (15, 100, 80), (35, 255, 255))
    green = cv2.inRange(hsv, (40, 100, 80), (90, 255, 255))
    r = (red1.mean() + red2.mean()) / 510.0
    y = yellow.mean() / 255.0
    g = green.mean() / 255.0
    m = max(r, y, g)
    if m < 0.02:
        return 'unknown'
    return 'den_do' if r == m else ('den_vang' if y == m else 'den_xanh')

# Global variables
LANE_CONFIGS = []
STOP_LINE = None  # Single stopline: (p1, p2)
_tmp_lane_pts = []
_tmp_stop_point = None
_tmp_tl_point = None  # For manual TL ROI selection
_drawing_mode = None  # 'lane' or 'stopline' or 'tl_manual' or 'direction_roi' or 'ref_vector' or None
_detection_running = False
_show_all_boxes = True  # True = show all vehicles, False = show only violators

# Detection variables
VIOLATOR_TRACK_IDS = set()
RED_LIGHT_VIOLATORS = set()
LANE_VIOLATORS = set()
PASSED_VEHICLES = set()  # Track vehicles that passed stop line
MOTORBIKE_COUNT = set()  # Track motorbikes (xe máy)
CAR_COUNT = set()  # Track cars/trucks/buses (ô tô, xe tải, xe bus)
VEHICLE_CLASSES = {0: "o to", 1: "xe bus", 2: "xe dap", 3: "xe may", 4: "xe tai"}  # Custom model classes
ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]

# =========================================
# 0. HÀM PHÂN LOẠI MÀU ĐÈN GIAO THÔNG
# =========================================
def classify_tl_color(roi):
    if roi is None or roi.size == 0:
        return "unknown"

    roi = cv2.resize(roi, (20, 60))
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 100, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 80])
    upper_red2 = np.array([180, 255, 255])

    lower_yellow = np.array([15, 100, 80])
    upper_yellow = np.array([35, 255, 255])

    lower_green = np.array([40, 100, 80])
    upper_green = np.array([90, 255, 255])

    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | \
               cv2.inRange(hsv, lower_red2, upper_red2)
    mask_yel = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_grn = cv2.inRange(hsv, lower_green, upper_green)

    red_ratio = mask_red.mean() / 255.0
    yellow_ratio = mask_yel.mean() / 255.0
    green_ratio = mask_grn.mean() / 255.0

    if max(red_ratio, yellow_ratio, green_ratio) < 0.02:
        return "unknown"

    if red_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "red"
    elif yellow_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "yellow"
    else:
        return "green"

def point_in_polygon(point, poly):
    x, y = point
    pts = np.array(poly, dtype=np.int32)
    return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0

def point_to_segment_distance(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return np.sqrt((px - x1)**2 + (py - y1)**2)
    t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return np.sqrt((px - nx)**2 + (py - ny)**2)

def has_crossed_stopline(cx, cy, min_distance=5):
    """Kiểm tra xe đã VƯỢT QUA vạch dừng
    
    ⚠️ LOGIC MỚI: Tâm xe phải TRÙNG với vạch dừng (trong threshold) thì mới tính là crossed
    Điều này loại bỏ hoàn toàn xe đi ngang vì:
    - Xe đi ngang: cx thay đổi nhiều, cy gần như không đổi → cy KHÔNG trùng stopline_y
    - Xe đi từ dưới lên: cy giảm dần và SẼ trùng với stopline_y tại 1 thời điểm
    
    Args:
        cx, cy: Tọa độ tâm xe
        min_distance: Khoảng threshold cho "trùng vạch" (mặc định 5px)
    
    Returns:
        True nếu tâm xe TRÙNG với vạch dừng (trong khoảng threshold)
              VÀ xe nằm trong phạm vi x của vạch
        False nếu không trùng hoặc xe đi ngang
    """
    global STOP_LINE
    if STOP_LINE is None:
        return False
    
    p1, p2 = STOP_LINE
    
    # Tính y trung bình của vạch dừng
    stopline_y = (p1[1] + p2[1]) / 2
    
    # Tính phạm vi x của vạch dừng
    stopline_x_min = min(p1[0], p2[0])
    stopline_x_max = max(p1[0], p2[0])
    
    # ⚠️ CRITICAL 1: Xe phải nằm ĐÚNG trong phạm vi X của vạch dừng
    # Không cho margin → Chỉ bắt xe đi thẳng qua vạch
    if not (stopline_x_min <= cx <= stopline_x_max):
        return False  # Xe ngoài phạm vi vạch dừng
    
    # ⚠️ CRITICAL 2: CHỈ bắt xe KHI ĐÃ VƯỢT QUA vạch dừng
    # KHÔNG bắt xe đang tiến đến vạch (cy > stopline_y)
    # CHỈ bắt xe đã qua vạch một chút (cy < stopline_y)
    # 
    # Logic: Xe phải QUA vạch ít nhất 1px (cy <= stopline_y - 1)
    # VÀ không quá xa (trong vùng min_distance pixels)
    
    if cy <= stopline_y - 1:  # Xe đã qua vạch (ít nhất 1px)
        return True
    
    return False

def is_on_stop_line(cx, cy, threshold=80):
    """Check if point is on THE stopline
    
    Args:
        threshold: Khoảng cách cho phép (pixels)
                   Mặc định 80px để:
                   - Bù offset camera góc cao (~30-50px)
                   - Buffer an toàn (~30px)
                   → Tránh bắt sai khi xe còn cách vạch dừng
    """
    global STOP_LINE
    if STOP_LINE is None:
        return False
    p1, p2 = STOP_LINE
    dist = point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
    return dist < threshold

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
    import math
    
    if track_id not in VEHICLE_POSITIONS:
        VEHICLE_POSITIONS[track_id] = []
    
    # Add current position with timestamp
    import time
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
        pixel_to_meter: Calibration factor (default 0.05 meters per pixel)
    
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
    
    # ✅ FIX: Dùng allowed_directions thay vì primary + secondary
    allowed_dirs = lane_roi.get('allowed_directions', [])
    
    # Backward compatibility: nếu không có allowed_directions, dùng primary_direction
    if not allowed_dirs:
        primary_dir = lane_roi.get('primary_direction', lane_roi.get('direction', 'unknown'))
        allowed_dirs = [primary_dir]
    
    if vehicle_direction not in allowed_dirs:
        allowed_str = ', '.join(allowed_dirs)
        return (True, f"🚨 VI PHẠM - Xe đi {vehicle_direction} (Chỉ được: {allowed_str})")
    
    return (False, f"✅ OK - Đi đúng hướng ({vehicle_direction})")

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
    
    VÍ DỤ FIX BUG:
    - Đèn rẽ trái đỏ + Đèn đi thẳng xanh + Xe đi thẳng = ✅ OK (không bị ảnh hưởng)
    - Đèn rẽ trái đỏ + Đèn tròn xanh + Xe rẽ trái = ❌ VI PHẠM (phải tuân theo đèn rẽ trái)
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
    # STEP 2: Xử lý RẼ PHẢI
    # ========================================
    if vehicle_direction == 'right':
        # Kiểm tra xem có đèn rẽ phải chuyên biệt không
        if lights_by_type['rẽ phải']:  # Có đèn rẽ phải chuyên biệt
            for light in lights_by_type['rẽ phải']:
                if light['color'] == 'xanh':
                    return (False, f"✅ RIGHT TURN - Green right arrow ALLOWED")
                elif light['color'] == 'đỏ':
                    # ⚠️ STRICT MODE: Nếu có đèn rẽ phải chuyên biệt đỏ → VI PHẠM
                    # (Tương tự rẽ trái - xe phải tuân theo đèn chuyên biệt)
                    other_lights = f"straight={'xanh' if any(l['color']=='xanh' for l in lights_by_type['đi thẳng']) else 'đỏ/off'}"
                    return (True, f"🚨 VI PHẠM - Đèn rẽ phải ĐỎ (xe rẽ phải phải tuân theo đèn rẽ phải, {other_lights})")
                # Vàng → bỏ qua, check đèn khác
        
        # Nếu KHÔNG có đèn rẽ phải chuyên biệt
        # → Theo luật VN: RẼ PHẢI ĐƯỢC PHÉP khi đèn đỏ
        return (False, f"✅ RIGHT TURN on RED - ALLOWED by VN law (no right arrow, Điều 7, TT 65/2015)")
    
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
                    # ⚠️ CRITICAL: Xe rẽ trái khi đèn rẽ trái đỏ = VI PHẠM
                    # (Dù đèn thẳng có xanh cũng không được phép!)
                    other_lights = f"straight={'xanh' if any(l['color']=='xanh' for l in lights_by_type['đi thẳng']) else 'đỏ/off'}"
                    return (True, f"🚨 VI PHẠM - Đèn rẽ trái ĐỎ (xe rẽ trái phải tuân theo đèn rẽ trái, {other_lights})")
                # Vàng → bỏ qua, check đèn khác
        
        # ⚠️ CRITICAL: Nếu có đèn đi thẳng xanh mà xe rẽ trái = VI PHẠM
        # (Đèn đi thẳng CHỈ cho đi thẳng, không cho rẽ trái)
        if lights_by_type['đi thẳng']:
            for light in lights_by_type['đi thẳng']:
                if light['color'] == 'xanh':
                    return (True, f"🚨 VI PHẠM - Đèn đi thẳng xanh CHỈ cho đi thẳng, KHÔNG cho rẽ trái")
                elif light['color'] == 'đỏ':
                    return (True, f"🚨 VI PHẠM - Đèn đi thẳng ĐỎ cấm rẽ trái")
    
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
    # Nếu đến đây nghĩa là:
    # - Xe đi thẳng: Không có đèn đi thẳng riêng HOẶC đèn đi thẳng vàng
    # - Xe rẽ trái: Không có đèn rẽ trái riêng HOẶC đèn rẽ trái vàng
    
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
                # Xe đi thẳng đã xử lý ở STEP 3
                    
            elif light['color'] == 'đỏ':
                # Đèn tròn đỏ → Cấm thẳng và rẽ trái (rẽ phải đã xử lý ở STEP 2)
                if vehicle_direction == 'left':
                    # ⚠️ XE RẼ TRÁI: Kiểm tra xem có đèn rẽ trái xanh không
                    has_left_green = any(l['color'] == 'xanh' for l in lights_by_type['rẽ trái'])
                    if has_left_green:
                        return (False, f"✅ LEFT TURN - Left arrow green ALLOWED")
                    return (True, f"🚨 VI PHẠM - Đèn tròn ĐỎ cấm rẽ trái")
                # Xe đi thẳng đã xử lý ở STEP 3
    
    # ========================================
    # STEP 5: Xử lý UNKNOWN direction
    # ========================================
    if vehicle_direction == 'unknown':
        # ⚠️ KHÔNG PHẠT khi không xác định được hướng (benefit of doubt)
        # Lý do: Xe có thể đang rẽ phải (hợp pháp) hoặc có lỗi direction detection
        # Tránh false positive
        all_lights = []
        for lights in lights_by_type.values():
            all_lights.extend(lights)
        
        has_any_green = any(l['color'] == 'xanh' for l in all_lights)
        
        if has_any_green:
            return (False, f"✅ Unknown direction but GREEN light exists - ALLOWED")
        else:
            # Ngay cả khi tất cả đèn đỏ, vẫn KHÔNG PHẠT vì có thể xe rẽ phải
            return (False, f"⚠️ Unknown direction - No violation (benefit of doubt)")
    
    # ========================================
    # STEP 6: Mặc định - Không phạt nếu không rõ
    # ========================================
    return (False, f"⚠️ No clear violation - dir={vehicle_direction}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Declare globals used in this method
        global VIOLATOR_TRACK_IDS, RED_LIGHT_VIOLATORS, LANE_VIOLATORS, PASSED_VEHICLES, MOTORBIKE_COUNT, CAR_COUNT
        global ALLOWED_VEHICLE_IDS, VEHICLE_CLASSES, LANE_CONFIGS, TL_ROIS, _show_all_boxes
        global DIRECTION_ROIS, _tmp_direction_roi_pts, _selected_direction
        
        # Initialize ROI Editor
        self.roi_editor = ROIEditor()
        
        # Ask user to select video FIRST before showing main UI
        video_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File to Start",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)"
        )
        
        if not video_path:
            # User cancelled - exit application
            print("❌ No video selected. Exiting...")
            QApplication.quit()
            return
        
        self.video_path = video_path
        print(f"📹 Selected video: {video_path}")
        
        # Now setup the UI
        self.setWindowTitle("Traffic Violation by dangdoday")
        self.setGeometry(50, 50, 1600, 900)
        
        # Pre-load YOLO model in main thread to avoid DLL issues in QThread
        self.yolo_model = None
        self.current_model_type = None
        self.current_model_config = None
        
        # Try to migrate old weights first
        migrate_old_weights()
        
        # Scan available models
        self.available_models = scan_all_models()
        print(f"📦 Available models: {list(self.available_models.keys())}")
        
        # Setup menu bar AFTER available_models is initialized
        self.setup_menu_bar()
        
        # Auto-load first available model
        if YOLO_AVAILABLE and self.available_models:
            first_model_type = list(self.available_models.keys())[0]
            first_weight = self.available_models[first_model_type]["weights"][0]
            self.load_model(first_model_type, first_weight)
        else:
            print("⚠️ YOLO not available or no models found, detection disabled")
        
        # Initialize TL tracking (manual ROI only, no auto-detection)
        self.tl_tracking_active = False  # Continuous color tracking flag
        self.tl_color_frame_count = 0  # Counter for color update throttling
        self.cap = None  # Will be set when video loads
        print("✅ Manual TL ROI mode enabled")
        
        # View toggle flags
        self.show_lanes_flag = True
        self.show_stopline_flag = True
        self.show_traffic_lights_flag = True
        self.show_ref_vector_flag = True
        
        # Lane editing state
        self.editing_lane_idx = None
        self.dragging_lane_point_idx = None
        
        # Initialize display scale variables for accurate click detection
        self.current_display_scale = 1.0
        self.current_display_width = 1024
        self.current_display_height = 768
        self.current_display_offset_x = 0
        self.current_display_offset_y = 0
        
        # Main layout
        main_layout = QHBoxLayout()
        
        # Left side - Video display
        self.video_label = QLabel()
        self.video_label.setScaledContents(False)
        self.video_label.setMinimumSize(1024, 768)
        self.video_label.mousePressEvent = self.video_mouse_press
        self.video_label.mouseMoveEvent = self.video_mouse_move
        self.video_label.mouseReleaseEvent = self.video_mouse_release
        self.video_label.mouseDoubleClickEvent = self.video_mouse_double_click
        
        # Enable context menu on video label
        self.video_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_label.customContextMenuRequested.connect(self.show_context_menu)
        
        main_layout.addWidget(self.video_label)
        
        # Right side - Control panel
        control_layout = QVBoxLayout()
        
        # Model selection
        control_layout.addWidget(QLabel("Model Selection"))
        
        self.model_type_combo = QComboBox()
        for model_type, info in self.available_models.items():
            self.model_type_combo.addItem(f"{model_type} - {info['config']['description']}")
        self.model_type_combo.currentIndexChanged.connect(self.on_model_type_changed)
        control_layout.addWidget(self.model_type_combo)
        
        self.weight_combo = QComboBox()
        self.update_weight_combo()
        self.weight_combo.currentIndexChanged.connect(self.on_weight_changed)
        control_layout.addWidget(self.weight_combo)
        
        self.model_info_label = QLabel("")
        self.update_model_info_label()
        control_layout.addWidget(self.model_info_label)
        
        # Model parameters
        control_layout.addWidget(QLabel("Detection Parameters"))
        
        # Image size control
        imgsz_layout = QHBoxLayout()
        imgsz_layout.addWidget(QLabel("ImgSize:"))
        self.imgsz_spinbox = QSpinBox()
        self.imgsz_spinbox.setMinimum(320)
        self.imgsz_spinbox.setMaximum(1280)
        self.imgsz_spinbox.setSingleStep(32)
        self.imgsz_spinbox.setValue(416 if self.current_model_config else 416)
        self.imgsz_spinbox.valueChanged.connect(self.on_imgsz_changed)
        imgsz_layout.addWidget(self.imgsz_spinbox)
        control_layout.addLayout(imgsz_layout)
        
        # Confidence threshold control
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        self.conf_spinbox = QDoubleSpinBox()
        self.conf_spinbox.setMinimum(0.1)
        self.conf_spinbox.setMaximum(0.95)
        self.conf_spinbox.setSingleStep(0.05)
        self.conf_spinbox.setDecimals(2)
        self.conf_spinbox.setValue(0.3 if self.current_model_config else 0.3)
        self.conf_spinbox.valueChanged.connect(self.on_conf_changed)
        conf_layout.addWidget(self.conf_spinbox)
        control_layout.addLayout(conf_layout)
        
        # Lane management
        control_layout.addWidget(QLabel("Lane Management"))
        
        self.btn_add_lane = QPushButton("Add Lane (Click on video)")
        self.btn_add_lane.clicked.connect(self.start_add_lane)
        control_layout.addWidget(self.btn_add_lane)
        
        self.btn_delete_lane = QPushButton("Delete Selected Lane")
        self.btn_delete_lane.clicked.connect(self.delete_lane)
        control_layout.addWidget(self.btn_delete_lane)
        
        # Stop line management
        control_layout.addWidget(QLabel("Stop Line (Single)"))
        
        self.btn_add_stopline = QPushButton("Set Stop Line (Click 2 points)")
        self.btn_add_stopline.clicked.connect(self.start_add_stopline)
        control_layout.addWidget(self.btn_add_stopline)
        
        self.btn_delete_stopline = QPushButton("Delete Stop Line")
        self.btn_delete_stopline.clicked.connect(self.delete_stopline)
        control_layout.addWidget(self.btn_delete_stopline)
        
        # Start detection
        self.btn_start = QPushButton("Start Detection")
        self.btn_start.clicked.connect(self.start_detection)
        control_layout.addWidget(self.btn_start)
        
        # Toggle bounding box display
        self.btn_toggle_bb = QPushButton("Show All Boxes: ON")
        self.btn_toggle_bb.setCheckable(True)
        self.btn_toggle_bb.setChecked(True)
        self.btn_toggle_bb.clicked.connect(self.toggle_bbox_display)
        control_layout.addWidget(self.btn_toggle_bb)
        
        # Select video button
        self.btn_select_video = QPushButton("Select Video File")
        self.btn_select_video.clicked.connect(self.select_video)
        control_layout.addWidget(self.btn_select_video)

        # Traffic light tools
        self.btn_find_tl = QPushButton("Add Traffic Light (Draw ROI)")
        self.btn_find_tl.clicked.connect(self.find_tl_roi)
        control_layout.addWidget(self.btn_find_tl)
        
        self.btn_delete_tl = QPushButton("Delete Traffic Light")
        self.btn_delete_tl.clicked.connect(self.delete_tl)
        control_layout.addWidget(self.btn_delete_tl)
        
        # Direction Detection tools
        control_layout.addWidget(QLabel("Direction ROI Management"))
        
        # Direction selector (dropdown instead of keyboard)
        dir_select_layout = QHBoxLayout()
        dir_select_layout.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["left", "straight", "right"])
        self.direction_combo.setCurrentText("straight")
        self.direction_combo.currentTextChanged.connect(self.on_direction_changed)
        dir_select_layout.addWidget(self.direction_combo)
        control_layout.addLayout(dir_select_layout)
        
        self.btn_add_direction_roi = QPushButton("Draw Direction ROI (Click points)")
        self.btn_add_direction_roi.clicked.connect(self.start_add_direction_roi)
        control_layout.addWidget(self.btn_add_direction_roi)
        
        self.btn_finish_direction_roi = QPushButton("Finish Direction ROI")
        self.btn_finish_direction_roi.clicked.connect(self.finish_direction_roi)
        self.btn_finish_direction_roi.setEnabled(False)
        control_layout.addWidget(self.btn_finish_direction_roi)
        
        self.btn_delete_direction_roi = QPushButton("Delete Selected Direction ROI")
        self.btn_delete_direction_roi.clicked.connect(self.delete_direction_roi)
        control_layout.addWidget(self.btn_delete_direction_roi)
        
        # Edit Direction ROI tool
        self.btn_edit_direction_roi = QPushButton("Edit Selected Direction ROI")
        self.btn_edit_direction_roi.clicked.connect(self.start_edit_direction_roi)
        control_layout.addWidget(self.btn_edit_direction_roi)
        
        self.btn_finish_edit_roi = QPushButton("Finish Editing ROI")
        self.btn_finish_edit_roi.clicked.connect(self.finish_edit_roi)
        self.btn_finish_edit_roi.setEnabled(False)
        control_layout.addWidget(self.btn_finish_edit_roi)
        
        self.btn_smooth_roi = QPushButton("Smooth ROI (reduce points)")
        self.btn_smooth_roi.clicked.connect(self.smooth_current_roi)
        self.btn_smooth_roi.setEnabled(False)
        control_layout.addWidget(self.btn_smooth_roi)
        
        self.btn_change_roi_direction = QPushButton("Change ROI Directions")
        self.btn_change_roi_direction.clicked.connect(self.change_roi_directions)
        self.btn_change_roi_direction.setEnabled(False)
        control_layout.addWidget(self.btn_change_roi_direction)
        
        # Toggle show direction ROIs
        self.btn_toggle_direction_rois = QPushButton("Show Direction ROIs: ON")
        self.btn_toggle_direction_rois.setCheckable(True)
        self.btn_toggle_direction_rois.setChecked(True)
        self.btn_toggle_direction_rois.clicked.connect(self.toggle_direction_rois)
        control_layout.addWidget(self.btn_toggle_direction_rois)
        
        # Reference Vector (for camera nghiêng)
        control_layout.addWidget(QLabel("Reference Vector (Camera Tilted)"))
        
        self.btn_set_ref_vector = QPushButton("Set Reference Vector (2 points)")
        self.btn_set_ref_vector.clicked.connect(self.start_set_reference_vector)
        control_layout.addWidget(self.btn_set_ref_vector)
        
        self.btn_finish_ref_vector = QPushButton("Finish Reference Vector")
        self.btn_finish_ref_vector.clicked.connect(self.finish_reference_vector)
        self.btn_finish_ref_vector.setEnabled(False)
        control_layout.addWidget(self.btn_finish_ref_vector)
        
        self.ref_vector_label = QLabel("⚠️ Ref Vector: Not set - Required for turn detection!")
        self.ref_vector_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
        self.ref_vector_label.setWordWrap(True)
        control_layout.addWidget(self.ref_vector_label)
        
        # Add helpful hint
        ref_vector_hint = QLabel("💡 Hint: Click 2 points on a STRAIGHT lane\n(from start to end in traffic flow direction)")
        ref_vector_hint.setStyleSheet("QLabel { color: gray; font-size: 9pt; font-style: italic; }")
        ref_vector_hint.setWordWrap(True)
        control_layout.addWidget(ref_vector_hint)
        
        self.show_direction_rois = True
        self.show_lanes = True  # Toggle for lane display
        self.show_roi_overlays = True  # Toggle for ROI overlay display
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        
        # Config Manager
        self.config_manager = ConfigManager()
        
        # Save/Load Configuration buttons
        control_layout.addWidget(QLabel("Configuration Management"))
        
        self.btn_save_config = QPushButton("💾 Save All ROIs Configuration")
        self.btn_save_config.clicked.connect(self.save_configuration)
        self.btn_save_config.setStyleSheet("QPushButton { font-weight: bold; background-color: #4CAF50; color: white; }")
        control_layout.addWidget(self.btn_save_config)
        
        self.btn_load_config = QPushButton("📂 Load Configuration")
        self.btn_load_config.clicked.connect(self.load_configuration)
        control_layout.addWidget(self.btn_load_config)
        
        self.config_status_label = QLabel("Config: Not loaded")
        self.config_status_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        control_layout.addWidget(self.config_status_label)
        
        self.status_label = QLabel("Status: Ready - Direction-based detection")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # Hide control panel - all controls moved to menu bar
        # main_layout.addLayout(control_layout)  # COMMENTED OUT
        
        # Add status bar instead
        self.statusBar().showMessage("Ready - Direction-based detection")
        
        # Create central widget and set layout (video only)
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Store control_layout reference for future use if needed
        self.control_layout = control_layout
        self.control_panel_visible = False
        
        # Video thread - start with selected video
        self.thread = VideoThread(self.video_path)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.error_signal.connect(self.show_error)
        
        # Pass globals reference to thread
        # Use lambda for _show_all_boxes to get real-time value
        self.thread.set_globals_reference({
            'ALLOWED_VEHICLE_IDS': ALLOWED_VEHICLE_IDS,
            'VEHICLE_CLASSES': VEHICLE_CLASSES,
            'LANE_CONFIGS': LANE_CONFIGS,
            'TL_ROIS': TL_ROIS,
            'DIRECTION_ROIS': DIRECTION_ROIS,
            'get_show_all_boxes': lambda: globals()['_show_all_boxes'],
            'is_on_stop_line': is_on_stop_line,
            'has_crossed_stopline': has_crossed_stopline,
            'check_tl_violation': check_tl_violation,
            'point_in_polygon': point_in_polygon,
            'VIOLATOR_TRACK_IDS': VIOLATOR_TRACK_IDS,
            'RED_LIGHT_VIOLATORS': RED_LIGHT_VIOLATORS,
            'LANE_VIOLATORS': LANE_VIOLATORS,
            'PASSED_VEHICLES': PASSED_VEHICLES,
            'MOTORBIKE_COUNT': MOTORBIKE_COUNT,
            'CAR_COUNT': CAR_COUNT
        })
        
        # Set model and config to thread if loaded
        if self.yolo_model is not None:
            self.thread.set_model(self.yolo_model)
            self.thread.model_config = self.current_model_config
        
        self.thread.start()
        
        # Initialize cap and current_frame for TL detection
        self.current_frame = None
        self.cap = cv2.VideoCapture(self.video_path)
        
        # Wait for first frame before auto-detect
        import time
        time.sleep(0.5)  # Wait for video thread to emit first frame
        
        # Trigger auto-detect after first frame is ready
        if self.cap.isOpened():
            ret, first_frame = self.cap.read()
            if ret:
                self.current_frame = first_frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start
        
        # No auto-detect - user will draw TL ROIs manually
        self.update_lists()
    
    def show_context_menu(self, pos):
        """Show context menu on video area with organized actions"""
        if self.current_frame is None:
            return
        
        menu = QMenu(self)
        
        # === DRAWING MODE Section ===
        drawing_menu = menu.addMenu("🎨 Drawing Mode")
        
        # Lane drawing
        action_draw_lane = QAction("Add Lane (polygon)", self)
        action_draw_lane.triggered.connect(self.start_add_lane)
        drawing_menu.addAction(action_draw_lane)
        
        # Stopline drawing
        action_draw_stopline = QAction("Set Stop Line (2 points)", self)
        action_draw_stopline.triggered.connect(self.start_add_stopline)
        drawing_menu.addAction(action_draw_stopline)
        
        # Traffic light
        action_draw_tl = QAction("Add Traffic Light (draw ROI)", self)
        action_draw_tl.triggered.connect(self.find_tl_roi)
        drawing_menu.addAction(action_draw_tl)
        
        # Direction ROI
        action_draw_direction = QAction("Draw Direction ROI (polygon)", self)
        action_draw_direction.triggered.connect(self.start_add_direction_roi)
        drawing_menu.addAction(action_draw_direction)
        
        # Reference vector
        drawing_menu.addSeparator()
        action_ref_vector = QAction("Set Reference Vector (2 points)", self)
        action_ref_vector.triggered.connect(self.start_set_reference_vector)
        drawing_menu.addAction(action_ref_vector)
        
        menu.addSeparator()
        
        # === EDIT MODE Section ===
        edit_menu = menu.addMenu("✏️ Edit Mode")
        
        # Edit direction ROI
        action_edit_direction = QAction("Edit Selected Direction ROI", self)
        action_edit_direction.triggered.connect(self.start_edit_direction_roi)
        action_edit_direction.setEnabled(len(DIRECTION_ROIS) > 0)
        edit_menu.addAction(action_edit_direction)
        
        # Smooth ROI
        action_smooth = QAction("Smooth ROI (reduce points)", self)
        action_smooth.triggered.connect(self.smooth_current_roi)
        action_smooth.setEnabled(self.roi_editor.is_editing())
        edit_menu.addAction(action_smooth)
        
        # Change directions
        action_change_dir = QAction("Change ROI Directions", self)
        action_change_dir.triggered.connect(self.change_roi_directions)
        action_change_dir.setEnabled(self.roi_editor.is_editing())
        edit_menu.addAction(action_change_dir)
        
        edit_menu.addSeparator()
        
        # Finish editing
        action_finish_edit = QAction("Finish Editing ROI", self)
        action_finish_edit.triggered.connect(self.finish_edit_roi)
        action_finish_edit.setEnabled(self.roi_editor.is_editing())
        edit_menu.addAction(action_finish_edit)
        
        menu.addSeparator()
        
        # === DELETE Section ===
        delete_menu = menu.addMenu("🗑️ Delete")
        
        action_delete_lane = QAction("Delete Selected Lane", self)
        action_delete_lane.triggered.connect(self.delete_lane)
        action_delete_lane.setEnabled(len(LANE_CONFIGS) > 0)
        delete_menu.addAction(action_delete_lane)
        
        action_delete_stopline = QAction("Delete Stop Line", self)
        action_delete_stopline.triggered.connect(self.delete_stopline)
        action_delete_stopline.setEnabled(STOP_LINE is not None)
        delete_menu.addAction(action_delete_stopline)
        
        action_delete_tl = QAction("Delete Traffic Light", self)
        action_delete_tl.triggered.connect(self.delete_tl)
        action_delete_tl.setEnabled(len(TL_ROIS) > 0)
        delete_menu.addAction(action_delete_tl)
        
        action_delete_direction = QAction("Delete Direction ROI", self)
        action_delete_direction.triggered.connect(self.delete_direction_roi)
        action_delete_direction.setEnabled(len(DIRECTION_ROIS) > 0)
        delete_menu.addAction(action_delete_direction)
        
        menu.addSeparator()
        
        # === VIEW Section ===
        view_menu = menu.addMenu("👁️ View Options")
        
        # Toggle direction ROIs
        action_toggle_dir = QAction("Toggle Direction ROIs", self)
        action_toggle_dir.setCheckable(True)
        action_toggle_dir.setChecked(self.show_direction_rois)
        action_toggle_dir.triggered.connect(self.toggle_direction_rois)
        view_menu.addAction(action_toggle_dir)
        
        # Toggle all boxes
        action_toggle_boxes = QAction("Show All Bounding Boxes", self)
        action_toggle_boxes.setCheckable(True)
        action_toggle_boxes.setChecked(_show_all_boxes)
        action_toggle_boxes.triggered.connect(self.toggle_bbox_display)
        view_menu.addAction(action_toggle_boxes)
        
        menu.addSeparator()
        
        # === CONFIG Section ===
        config_menu = menu.addMenu("💾 Configuration")
        
        action_save_config = QAction("Save All ROIs Configuration", self)
        action_save_config.triggered.connect(self.save_configuration)
        config_menu.addAction(action_save_config)
        
        action_load_config = QAction("Load Configuration", self)
        action_load_config.triggered.connect(self.load_configuration)
        config_menu.addAction(action_load_config)
        
        # Show menu at cursor position
        menu.exec_(self.video_label.mapToGlobal(pos))
        
    def video_mouse_press(self, event):
        global _drawing_mode, _tmp_lane_pts, _tmp_stop_point, LANE_CONFIGS, STOP_LINE
        global _tmp_direction_roi_pts, DIRECTION_ROIS
        
        if self.current_frame is None:
            return
        
        from PyQt5.QtCore import Qt
        
        # Use stored scale information for accurate click detection
        if not hasattr(self, 'current_display_scale'):
            return
        
        # Get click position relative to label
        click_x = event.pos().x() - self.current_display_offset_x
        click_y = event.pos().y() - self.current_display_offset_y
        
        # Convert to frame coordinates using stored scale
        if 0 <= click_x < self.current_display_width and 0 <= click_y < self.current_display_height:
            frame_x = int(click_x / self.current_display_scale)
            frame_y = int(click_y / self.current_display_scale)
            
            # Handle lane editing mode
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                lane = LANE_CONFIGS[self.editing_lane_idx]
                points = lane['poly']
                
                # Right-click to delete point
                if event.button() == Qt.RightButton:
                    for i, (px, py) in enumerate(points):
                        dist = ((frame_x - px)**2 + (frame_y - py)**2) ** 0.5
                        if dist < 15:  # Within 15 pixels
                            if len(points) <= 3:
                                QMessageBox.warning(self, "Minimum Points", "Lane must have at least 3 points!")
                                return
                            del points[i]
                            self.update_lists()
                            print(f"🗑️ Deleted point {i+1} from Lane {self.editing_lane_idx+1}")
                            return
                    return
                
                # Left-click to start dragging
                if event.button() == Qt.LeftButton:
                    for i, (px, py) in enumerate(points):
                        dist = ((frame_x - px)**2 + (frame_y - py)**2) ** 0.5
                        if dist < 15:  # Within 15 pixels
                            self.dragging_lane_point_idx = i
                            print(f"🖱️ Started dragging point {i+1}")
                            return
                    
                    # If not dragging, treat as potential add point on mouse move
                    self.dragging_lane_point_idx = None
                return
            
            # Handle ROI editing mode
            if self.roi_editor.is_editing():
                roi_idx = self.roi_editor.editing_roi_index
                if roi_idx < len(DIRECTION_ROIS):
                    points = DIRECTION_ROIS[roi_idx]['points']
                    button_name = 'right' if event.button() == Qt.RightButton else 'left'
                    self.roi_editor.handle_mouse_press(frame_x, frame_y, button_name, points)
                return
            
            if _drawing_mode == 'lane':
                _tmp_lane_pts.append((frame_x, frame_y))
                print(f"📍 Điểm {len(_tmp_lane_pts)} của lane: ({frame_x}, {frame_y})")
            elif _drawing_mode == 'stopline':
                global STOP_LINE
                if _tmp_stop_point is None:
                    _tmp_stop_point = (frame_x, frame_y)
                    print(f"📍 Điểm đầu vạch dừng: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click second point for THE stop line")
                else:
                    p1 = _tmp_stop_point
                    p2 = (frame_x, frame_y)
                    STOP_LINE = (p1, p2)
                    print(f"🚦 Đã tạo vạch dừng: {p1} -> {p2}")
                    _tmp_stop_point = None
                    _drawing_mode = None
                    self.status_label.setText("Status: Stopline created. Direction tracking enabled.")
            elif _drawing_mode == 'direction_roi':
                # Add point to direction ROI
                _tmp_direction_roi_pts.append([frame_x, frame_y])
                print(f"📍 Direction ROI point {len(_tmp_direction_roi_pts)}: ({frame_x}, {frame_y})")
                self.status_label.setText(f"Status: Direction ROI - {len(_tmp_direction_roi_pts)} points. Click 'Finish' when done.")
            elif _drawing_mode == 'ref_vector':
                # Reference vector for camera nghiêng
                if self.ref_vector_p1 is None:
                    self.ref_vector_p1 = (frame_x, frame_y)
                    print(f"📍 Ref Vector P1: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click END point on straight lane")
                elif self.ref_vector_p2 is None:
                    self.ref_vector_p2 = (frame_x, frame_y)
                    print(f"📍 Ref Vector P2: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click 'Finish Reference Vector'")
            elif _drawing_mode == 'tl_manual':
                global _tmp_tl_point, TL_ROIS
                if _tmp_tl_point is None:
                    _tmp_tl_point = (frame_x, frame_y)
                    print(f"📍 TL ROI điểm 1: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click second point for TL ROI")
                else:
                    p1 = _tmp_tl_point
                    p2 = (frame_x, frame_y)
                    x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
                    x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
                    
                    # Ask user to select TL type
                    tl_types = ['đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải']
                    tl_type, ok = QInputDialog.getItem(
                        self,
                        "Select Traffic Light Type",
                        "Chọn loại đèn giao thông:",
                        tl_types,
                        editable=False
                    )
                    
                    if not ok:
                        # User cancelled - reset
                        _tmp_tl_point = None
                        _drawing_mode = None
                        self.status_label.setText("Status: TL selection cancelled")
                        return
                    
                    # Add to list with 6-tuple format (position + type + color) - NO stoplines
                    TL_ROIS.append((x1, y1, x2, y2, tl_type, 'unknown'))
                    print(f"🚦 TL ROI created: ({x1},{y1},{x2},{y2}) Type={tl_type}")
                    print(f"📍 Use vehicle direction to match with TL type")
                    
                    # Enable color tracking
                    self.tl_tracking_active = True
                    print("🚦 HSV color tracking started")
                    
                    _tmp_tl_point = None
                    _drawing_mode = None
                    
                    self.status_label.setText(f"Status: TL {len(TL_ROIS)} added ({tl_type}). Total: {len(TL_ROIS)} TL(s)")
                    self.btn_find_tl.setText("Add Traffic Light")
                    self.btn_find_tl.clicked.disconnect()
                    self.btn_find_tl.clicked.connect(self.find_tl_roi)
    
    def video_mouse_move(self, event):
        """Handle mouse move for dragging points and hover effects"""
        global DIRECTION_ROIS, LANE_CONFIGS
        
        if self.current_frame is None:
            return
        
        # Get mouse position in frame coordinates
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        frame_height, frame_width = self.current_frame.shape[:2]
        
        scale = min(label_width / frame_width, label_height / frame_height)
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
        offset_x = (label_width - display_width) // 2
        offset_y = (label_height - display_height) // 2
        
        mouse_x = event.pos().x() - offset_x
        mouse_y = event.pos().y() - offset_y
        
        if 0 <= mouse_x < display_width and 0 <= mouse_y < display_height:
            frame_x = int(mouse_x / scale)
            frame_y = int(mouse_y / scale)
            
            # Handle lane editing drag
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                if hasattr(self, 'dragging_lane_point_idx') and self.dragging_lane_point_idx is not None:
                    lane = LANE_CONFIGS[self.editing_lane_idx]
                    lane['poly'][self.dragging_lane_point_idx] = [frame_x, frame_y]
                    if hasattr(self, 'editing_lane_update_func'):
                        self.editing_lane_update_func()
                    self.update_lists()
                return
            
            # Handle ROI editing
            if not self.roi_editor.is_editing():
                return
        mouse_y = event.pos().y() - offset_y
        
        if 0 <= mouse_x < display_width and 0 <= mouse_y < display_height:
            frame_x = int(mouse_x / scale)
            frame_y = int(mouse_y / scale)
            
            roi_idx = self.roi_editor.editing_roi_index
            if roi_idx < len(DIRECTION_ROIS):
                points = DIRECTION_ROIS[roi_idx]['points']
                self.roi_editor.handle_mouse_move(frame_x, frame_y, points)
    
    def video_mouse_release(self, event):
        """Stop dragging point"""
        # Stop lane point dragging
        if hasattr(self, 'dragging_lane_point_idx'):
            if self.dragging_lane_point_idx is not None:
                print(f"✅ Finished dragging point {self.dragging_lane_point_idx + 1}")
            self.dragging_lane_point_idx = None
        
        # Stop ROI point dragging
        self.roi_editor.handle_mouse_release()
    
    def video_mouse_double_click(self, event):
        """Double-click on edge to insert new point, or handle lane editing"""
        global DIRECTION_ROIS, LANE_CONFIGS
        from PyQt5.QtCore import Qt
        
        if event.button() != Qt.LeftButton:
            return
        
        if self.current_frame is None:
            return
        
        # Get click position in frame coordinates
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        frame_height, frame_width = self.current_frame.shape[:2]
        
        scale = min(label_width / frame_width, label_height / frame_height)
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
        offset_x = (label_width - display_width) // 2
        offset_y = (label_height - display_height) // 2
        
        click_x = event.pos().x() - offset_x
        click_y = event.pos().y() - offset_y
        
        if 0 <= click_x < display_width and 0 <= click_y < display_height:
            frame_x = int(click_x / scale)
            frame_y = int(click_y / scale)
            
            # Handle lane editing
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                lane = LANE_CONFIGS[self.editing_lane_idx]
                points = lane['poly']
                
                # Check if clicked near existing point (drag mode) - within 15 pixels
                clicked_point_idx = None
                for i, (px, py) in enumerate(points):
                    dist = ((frame_x - px)**2 + (frame_y - py)**2) ** 0.5
                    if dist < 15:
                        clicked_point_idx = i
                        break
                
                if clicked_point_idx is not None:
                    # Drag existing point
                    points[clicked_point_idx] = [frame_x, frame_y]
                    print(f"🖱️ Dragged point {clicked_point_idx+1} to ({frame_x}, {frame_y})")
                else:
                    # Add new point by finding closest edge
                    min_dist = float('inf')
                    insert_idx = None
                    
                    for i in range(len(points)):
                        p1 = points[i]
                        p2 = points[(i + 1) % len(points)]
                        
                        # Calculate distance to edge
                        edge_dist = self._point_to_line_distance(frame_x, frame_y, p1, p2)
                        if edge_dist < min_dist:
                            min_dist = edge_dist
                            insert_idx = i + 1
                    
                    if min_dist < 20:  # Only insert if close to an edge
                        points.insert(insert_idx, [frame_x, frame_y])
                        print(f"➕ Added new point at ({frame_x}, {frame_y}) after point {insert_idx}")
                
                # Update the keypoint list in dialog
                if hasattr(self, 'editing_lane_update_func'):
                    self.editing_lane_update_func()
                self.update_lists()
                return
            
            # Handle direction ROI editing
            if self.roi_editor.is_editing():
                roi_idx = self.roi_editor.editing_roi_index
                if roi_idx < len(DIRECTION_ROIS):
                    points = DIRECTION_ROIS[roi_idx]['points']
                    if self.roi_editor.handle_double_click(frame_x, frame_y, points):
                        pass  # List widget removed
    
    def _point_to_line_distance(self, px, py, p1, p2):
        """Calculate perpendicular distance from point to line segment"""
        x1, y1 = p1
        x2, y2 = p2
        
        # Vector from p1 to p2
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return ((px - x1)**2 + (py - y1)**2) ** 0.5
        
        # Parameter t for projection
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)))
        
        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        return ((px - closest_x)**2 + (py - closest_y)**2) ** 0.5
        
    def update_image(self, frame):
        global _tmp_lane_pts, _tmp_stop_point, _drawing_mode, _detection_running
        global _tmp_direction_roi_pts
        
        self.current_frame = frame.copy()
        display = frame.copy()
        
        # Update TL colors continuously (HSV pixel counting)
        self.update_tl_colors(display)
        
        # Draw direction ROIs (if enabled)
        if self.show_direction_rois and self.show_roi_overlays:
            display = self.draw_direction_rois(display)
        
        # Draw lanes (if enabled)
        if self.show_lanes and self.show_lanes_flag:
            display = self.draw_lanes(display)
        
        # Draw stop line (if enabled)
        if self.show_lanes and self.show_stopline_flag:
            display = self.draw_stop_line(display)
        
        # Draw temporary lane
        if _drawing_mode == 'lane' and len(_tmp_lane_pts) > 0:
            pts_tmp = np.array(_tmp_lane_pts, dtype=np.int32)
            cv2.polylines(display, [pts_tmp], isClosed=False, color=(0, 255, 0), thickness=2)
            for p in _tmp_lane_pts:
                cv2.circle(display, p, 4, (0, 255, 0), -1)
        
        # Draw temporary stop line point
        if _drawing_mode == 'stopline' and _tmp_stop_point is not None:
            cv2.circle(display, _tmp_stop_point, 5, (0, 0, 255), -1)
        
        # Draw temporary direction ROI
        if _drawing_mode == 'direction_roi' and len(_tmp_direction_roi_pts) > 0:
            DIRECTION_COLORS = {
                'left': (0, 0, 255),
                'right': (0, 165, 255),
                'straight': (0, 255, 0)
            }
            color = DIRECTION_COLORS.get(_selected_direction, (128, 128, 128))
            pts_tmp = np.array(_tmp_direction_roi_pts, dtype=np.int32)
            cv2.polylines(display, [pts_tmp], isClosed=False, color=color, thickness=2)
            for p in _tmp_direction_roi_pts:
                cv2.circle(display, tuple(p), 5, color, -1)
        
        # Draw temporary TL point
        if _drawing_mode == 'tl_manual' and _tmp_tl_point is not None:
            cv2.circle(display, _tmp_tl_point, 6, (0, 200, 255), -1)
            cv2.putText(display, "P1", (_tmp_tl_point[0]+8, _tmp_tl_point[1]), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)
        
        # Draw reference vector (for direction calibration) - check toggle flag
        if self.show_ref_vector_flag:
            if self.ref_vector_p1 is not None and self.ref_vector_p2 is not None:
                import math
                p1 = self.ref_vector_p1
                p2 = self.ref_vector_p2
                # Draw arrow showing reference direction
                cv2.arrowedLine(display, p1, p2, (255, 0, 255), 3, tipLength=0.05)
                # Draw start/end points
                cv2.circle(display, p1, 6, (255, 0, 255), -1)
                cv2.circle(display, p2, 6, (255, 0, 255), -1)
                # Draw label with angle
                mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                angle = math.degrees(math.atan2(dy, dx))
                cv2.putText(display, f"REF: {angle:.1f} deg", (mid[0] + 10, mid[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA)
        # Always show first point when drawing (regardless of toggle)
        if _drawing_mode == 'ref_vector' and self.ref_vector_p1 is not None:
            # Show first point while waiting for second
            cv2.circle(display, self.ref_vector_p1, 6, (255, 0, 255), -1)
            cv2.putText(display, "Click second point", (self.ref_vector_p1[0] + 10, self.ref_vector_p1[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2, cv2.LINE_AA)
        
        # Overlay ALL TL ROIs and labels (if enabled)
        global TL_ROIS
        if self.show_traffic_lights_flag:
            for idx, tl_data in enumerate(TL_ROIS):
                x1, y1, x2, y2, tl_type, current_color = tl_data
                # Color code by current light color
                box_color = (128, 128, 128)  # Gray default
                if current_color == 'đỏ':
                    box_color = (0, 0, 255)  # Red
                    color_display = "DO"
                elif current_color == 'xanh':
                    box_color = (0, 255, 0)  # Green
                    color_display = "XANH"
                elif current_color == 'vàng':
                    box_color = (0, 255, 255)  # Yellow
                    color_display = "VANG"
                else:
                    color_display = "???"
                
                # Map tl_type to ASCII for display
                if tl_type == 'tròn':
                    type_display = "tron"
                elif tl_type == 'đi thẳng':
                    type_display = "thang"
                elif tl_type == 'rẽ trái':
                    type_display = "L"
                elif tl_type == 'rẽ phải':
                    type_display = "R"
                else:
                    type_display = tl_type
                
                cv2.rectangle(display, (x1, y1), (x2, y2), box_color, 2)
                label_text = f"TL{idx+1}[{type_display}]: {color_display}"
                cv2.putText(display, label_text, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2, cv2.LINE_AA)
        
        # Convert to QImage
        rgb_image = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Scale to fit label while maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), 
            self.video_label.height(), 
            aspectRatioMode=1  # Keep aspect ratio
        )
        
        # Store scale information for accurate click detection
        self.current_display_scale = min(
            self.video_label.width() / w,
            self.video_label.height() / h
        )
        self.current_display_width = int(w * self.current_display_scale)
        self.current_display_height = int(h * self.current_display_scale)
        self.current_display_offset_x = (self.video_label.width() - self.current_display_width) // 2
        self.current_display_offset_y = (self.video_label.height() - self.current_display_height) // 2
        
        self.video_label.setPixmap(scaled_pixmap)
        
    def draw_lanes(self, frame):
        overlay = frame.copy()
        for idx, lane in enumerate(LANE_CONFIGS, start=1):
            poly = lane["poly"]
            pts = np.array(poly, dtype=np.int32)
            
            # Highlight lane being edited
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx == (idx - 1):
                # Draw in bright green with thicker outline
                cv2.fillPoly(overlay, [pts], (0, 255, 0))
                cv2.polylines(overlay, [pts], isClosed=True, color=(0, 200, 0), thickness=4)
                # Draw keypoints as circles
                for px, py in poly:
                    cv2.circle(overlay, (px, py), 8, (255, 0, 255), -1)
                    cv2.circle(overlay, (px, py), 8, (255, 255, 255), 2)
            else:
                # Normal lane rendering
                cv2.fillPoly(overlay, [pts], (0, 255, 255))
                cv2.polylines(overlay, [pts], isClosed=True, color=(0, 200, 200), thickness=2)
            
            cx = int(sum(p[0] for p in poly) / len(poly))
            cy = int(sum(p[1] for p in poly) / len(poly))
            cv2.putText(overlay, f"L{idx}", (cx-15, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        alpha = 0.3
        out = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        return out
    
    def draw_stop_line(self, frame):
        """Draw THE stop line"""
        global STOP_LINE
        if STOP_LINE is not None:
            p1, p2 = STOP_LINE
            cv2.line(frame, p1, p2, (0, 0, 255), 4)
            cv2.putText(frame, "STOP LINE", (p1[0], p1[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame
    
    def draw_direction_rois(self, frame):
        """Draw direction ROIs with transparency"""
        global DIRECTION_ROIS
        
        if not DIRECTION_ROIS:
            return frame
        
        overlay = frame.copy()
        
        DIRECTION_COLORS = {
            'left': (0, 0, 255),      # Đỏ
            'right': (0, 165, 255),   # Vàng
            'straight': (0, 255, 0),  # Xanh
            'unknown': (128, 128, 128)
        }
        
        # Vietnamese labels without accents
        DIRECTION_LABELS = {
            'left': 'RE TRAI',
            'right': 'RE PHAI', 
            'straight': 'DI THANG',
            'unknown': 'UNKNOWN'
        }
        
        for i, roi in enumerate(DIRECTION_ROIS):
            pts = np.array(roi['points'], dtype=np.int32)
            color = DIRECTION_COLORS.get(roi['direction'], DIRECTION_COLORS['unknown'])
            
            # Fill polygon với độ trong suốt
            cv2.fillPoly(overlay, [pts], color)
            
            # Vẽ viền
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Vẽ label ở giữa ROI
            center_x = int(np.mean([p[0] for p in roi['points']]))
            center_y = int(np.mean([p[1] for p in roi['points']]))
            
            direction_text = DIRECTION_LABELS.get(roi['direction'], roi['direction'].upper())
            cv2.putText(frame, direction_text, (center_x - 50, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Blend overlay với frame
        alpha = 0.25
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        # Draw editing overlay if in edit mode
        if self.roi_editor.is_editing():
            roi_idx = self.roi_editor.editing_roi_index
            if roi_idx < len(DIRECTION_ROIS):
                points = DIRECTION_ROIS[roi_idx]['points']
                self.roi_editor.draw_editing_overlay(frame, points)
        
        return frame
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for finishing drawings"""
        from PyQt5.QtCore import Qt
        global _drawing_mode, LANE_CONFIGS
        
        # Enter/Return key to finish drawing or editing
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Check if editing lane
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                self.finish_edit_lane()
                return
            # Check if editing ROI
            elif self.roi_editor.is_editing():
                self.finish_edit_roi()
                return
            # Check drawing modes
            elif _drawing_mode == 'lane':
                self.finish_lane()
                return
            elif _drawing_mode == 'direction_roi':
                self.finish_direction_roi()
                return
            elif _drawing_mode == 'ref_vector':
                self.finish_reference_vector()
                return
        
        # Delete key to remove point during lane editing
        if event.key() == Qt.Key_Delete:
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                # Find selected point (closest to last mouse position if available)
                # For now, just show message to use double-click instead
                QMessageBox.information(
                    self, 
                    "Delete Point", 
                    "To delete a point:\n\n"
                    "• Right-click directly on the point you want to delete\n"
                    "• The point must be within 15 pixels of your click"
                )
                return
        
        # Call parent class handler for other keys
        super().keyPressEvent(event)
    
    def start_add_lane(self):
        global _drawing_mode, _tmp_lane_pts
        _drawing_mode = 'lane'
        _tmp_lane_pts = []
        self.status_label.setText("Status: Click on video to draw lane. Press 'Finish Lane' or ENTER when done.")
        self.btn_add_lane.setText("Finish Lane (n)")
        self.btn_add_lane.clicked.disconnect()
        self.btn_add_lane.clicked.connect(self.finish_lane)
        
    def finish_lane(self):
        global _drawing_mode, _tmp_lane_pts, LANE_CONFIGS
        
        if len(_tmp_lane_pts) < 3:
            self.status_label.setText("Status: Need at least 3 points for a lane")
            return
            
        poly = _tmp_lane_pts.copy()
        print(f"✅ Created lane with {len(poly)} points")
        
        # Show vehicle type dialog
        dialog = VehicleTypeDialog(self)
        if dialog.exec_() == dialog.Accepted:
            allowed = dialog.get_selected()
            LANE_CONFIGS.append({
                "poly": poly,
                "allowed_labels": allowed
            })
            self.status_label.setText(f"Status: Lane added with vehicles: {', '.join(allowed)}")
        
        _tmp_lane_pts = []
        _drawing_mode = None
        self.btn_add_lane.setText("Add Lane (Click on video)")
        self.btn_add_lane.clicked.disconnect()
        self.btn_add_lane.clicked.connect(self.start_add_lane)
        self.update_lists()
        
    def start_add_stopline(self):
        global _drawing_mode, _tmp_stop_point, _tmp_lane_pts, STOP_LINE
        if STOP_LINE is not None:
            reply = QMessageBox.question(
                self,
                "Replace Stopline?",
                "Chỉ được có 1 vạch dừng. Bạn có muốn thay thế vạch cũ không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Reset lane drawing if in progress
        if _drawing_mode == 'lane':
            _tmp_lane_pts = []
            self.btn_add_lane.setText("Add Lane (Click on video)")
            self.btn_add_lane.clicked.disconnect()
            self.btn_add_lane.clicked.connect(self.start_add_lane)
        
        _drawing_mode = 'stopline'
        _tmp_stop_point = None
        self.status_label.setText("Status: Click 2 points for THE stop line")
        
    def delete_lane(self):
        """Delete selected lane - shows selection dialog"""
        global LANE_CONFIGS
        if not LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes to delete!")
            return
        
        # Show selection dialog
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout
        
        selection_dialog = QDialog(self)
        selection_dialog.setWindowTitle("Select Lane to Delete")
        sel_layout = QVBoxLayout(selection_dialog)
        
        sel_lane_list = QListWidget()
        for idx, lane in enumerate(LANE_CONFIGS):
            allowed = lane.get('allowed_labels', ['all'])
            sel_lane_list.addItem(f"Lane {idx+1}: {len(lane['poly'])} points - {', '.join(allowed)}")
        
        sel_layout.addWidget(QLabel("Select a lane to delete:"))
        sel_layout.addWidget(sel_lane_list)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Delete")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        sel_layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(selection_dialog.reject)
        
        def on_ok():
            sel_idx = sel_lane_list.currentRow()
            if sel_idx >= 0:
                selection_dialog.selected_idx = sel_idx
                selection_dialog.accept()
            else:
                QMessageBox.warning(selection_dialog, "No Selection", "Please select a lane!")
        
        btn_ok.clicked.connect(on_ok)
        
        if selection_dialog.exec_() == QDialog.Rejected:
            return
        
        selected = getattr(selection_dialog, 'selected_idx', -1)
        if selected >= 0 and selected < len(LANE_CONFIGS):
            del LANE_CONFIGS[selected]
            self.status_label.setText(f"Status: Deleted lane {selected + 1}")
            
    def delete_stopline(self):
        global STOP_LINE
        if STOP_LINE is None:
            self.status_label.setText("Status: No stopline to delete")
            QMessageBox.information(self, "No Stopline", "No stopline to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Stopline?",
            "Xóa vạch dừng?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            STOP_LINE = None
            self.status_label.setText("Status: Stopline deleted")
            print("🗑️ Stopline deleted")
            
    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point to line segment"""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1)**2 + (py - y1)**2)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
        nx = x1 + t * dx
        ny = y1 + t * dy
        return np.sqrt((px - nx)**2 + (py - ny)**2)
    
    def setup_menu_bar(self):
        """Setup menu bar with organized menus"""
        menubar = self.menuBar()
        
        # === FILE Menu ===
        file_menu = menubar.addMenu("📁 &File")
        
        # Select video
        action_select_video = QAction("Open Video...", self)
        action_select_video.setShortcut("Ctrl+O")
        action_select_video.triggered.connect(self.select_video)
        file_menu.addAction(action_select_video)
        
        file_menu.addSeparator()
        
        # Save/Load config
        action_save_config = QAction("💾 Save Configuration", self)
        action_save_config.setShortcut("Ctrl+S")
        action_save_config.triggered.connect(self.save_configuration)
        file_menu.addAction(action_save_config)
        
        action_load_config = QAction("📂 Load Configuration", self)
        action_load_config.setShortcut("Ctrl+L")
        action_load_config.triggered.connect(self.load_configuration)
        file_menu.addAction(action_load_config)
        
        file_menu.addSeparator()
        
        # Exit
        action_exit = QAction("Exit", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)
        
        # === DRAW Menu ===
        draw_menu = menubar.addMenu("🎨 &Draw")
        
        # Lane
        action_add_lane = QAction("Add Lane (Polygon)", self)
        action_add_lane.setShortcut("L")
        action_add_lane.triggered.connect(self.start_add_lane)
        draw_menu.addAction(action_add_lane)
        
        # Stopline
        action_add_stopline = QAction("Set Stop Line", self)
        action_add_stopline.setShortcut("S")
        action_add_stopline.triggered.connect(self.start_add_stopline)
        draw_menu.addAction(action_add_stopline)
        
        # Traffic light
        action_add_tl = QAction("Add Traffic Light", self)
        action_add_tl.setShortcut("T")
        action_add_tl.triggered.connect(self.find_tl_roi)
        draw_menu.addAction(action_add_tl)
        
        # Direction ROI
        action_add_direction = QAction("Draw Direction ROI", self)
        action_add_direction.setShortcut("D")
        action_add_direction.triggered.connect(self.start_add_direction_roi)
        draw_menu.addAction(action_add_direction)
        
        draw_menu.addSeparator()
        
        # Reference vector
        action_ref_vector = QAction("Set Reference Vector", self)
        action_ref_vector.setShortcut("R")
        action_ref_vector.triggered.connect(self.start_set_reference_vector)
        draw_menu.addAction(action_ref_vector)
        
        # === EDIT Menu ===
        edit_menu = menubar.addMenu("✏️ &Edit")
        
        # Edit Lane
        self.action_edit_lane = QAction("Edit Selected Lane", self)
        self.action_edit_lane.triggered.connect(self.start_edit_lane)
        edit_menu.addAction(self.action_edit_lane)
        
        # Edit direction ROI
        self.action_edit_direction = QAction("Edit Selected Direction ROI", self)
        self.action_edit_direction.setShortcut("E")
        self.action_edit_direction.triggered.connect(self.start_edit_direction_roi)
        edit_menu.addAction(self.action_edit_direction)
        
        # Smooth ROI
        self.action_smooth_roi = QAction("Smooth ROI", self)
        self.action_smooth_roi.triggered.connect(self.smooth_current_roi)
        self.action_smooth_roi.setEnabled(False)
        edit_menu.addAction(self.action_smooth_roi)
        
        # Change directions
        self.action_change_directions = QAction("Change ROI Directions", self)
        self.action_change_directions.triggered.connect(self.change_roi_directions)
        self.action_change_directions.setEnabled(False)
        edit_menu.addAction(self.action_change_directions)
        
        edit_menu.addSeparator()
        
        # Finish editing
        self.action_finish_edit = QAction("Finish Editing", self)
        self.action_finish_edit.setShortcut("Return")
        self.action_finish_edit.triggered.connect(self.finish_edit_roi)
        self.action_finish_edit.setEnabled(False)
        edit_menu.addAction(self.action_finish_edit)
        
        # === DELETE Menu ===
        delete_menu = menubar.addMenu("🗑️ De&lete")
        
        action_delete_lane = QAction("Delete Selected Lane", self)
        action_delete_lane.setShortcut("Delete")
        action_delete_lane.triggered.connect(self.delete_lane)
        delete_menu.addAction(action_delete_lane)
        
        action_delete_stopline = QAction("Delete Stop Line", self)
        action_delete_stopline.triggered.connect(self.delete_stopline)
        delete_menu.addAction(action_delete_stopline)
        
        action_delete_tl = QAction("Delete Traffic Light", self)
        action_delete_tl.triggered.connect(self.delete_tl)
        delete_menu.addAction(action_delete_tl)
        
        action_delete_direction = QAction("Delete Selected Direction ROI", self)
        action_delete_direction.triggered.connect(self.delete_direction_roi)
        delete_menu.addAction(action_delete_direction)
        
        # === VIEW Menu ===
        view_menu = menubar.addMenu("👁️ &View")
        
        # Toggle lanes
        self.action_toggle_lanes = QAction("Show Lanes", self)
        self.action_toggle_lanes.setCheckable(True)
        self.action_toggle_lanes.setChecked(True)
        self.action_toggle_lanes.triggered.connect(self.toggle_lanes)
        view_menu.addAction(self.action_toggle_lanes)
        
        # Toggle stopline
        self.action_toggle_stopline = QAction("Show Stop Line", self)
        self.action_toggle_stopline.setCheckable(True)
        self.action_toggle_stopline.setChecked(True)
        self.action_toggle_stopline.triggered.connect(self.toggle_stopline)
        view_menu.addAction(self.action_toggle_stopline)
        
        # Toggle traffic lights
        self.action_toggle_traffic_lights = QAction("Show Traffic Lights", self)
        self.action_toggle_traffic_lights.setCheckable(True)
        self.action_toggle_traffic_lights.setChecked(True)
        self.action_toggle_traffic_lights.triggered.connect(self.toggle_traffic_lights)
        view_menu.addAction(self.action_toggle_traffic_lights)
        
        # Toggle direction ROIs
        self.action_toggle_direction_rois = QAction("Show Direction ROIs", self)
        self.action_toggle_direction_rois.setCheckable(True)
        self.action_toggle_direction_rois.setChecked(True)
        self.action_toggle_direction_rois.triggered.connect(self.toggle_direction_rois)
        view_menu.addAction(self.action_toggle_direction_rois)
        
        # Toggle reference vector
        self.action_toggle_ref_vector = QAction("Show Reference Vector", self)
        self.action_toggle_ref_vector.setCheckable(True)
        self.action_toggle_ref_vector.setChecked(True)
        self.action_toggle_ref_vector.triggered.connect(self.toggle_ref_vector)
        view_menu.addAction(self.action_toggle_ref_vector)
        
        view_menu.addSeparator()
        
        # Toggle all boxes
        self.action_toggle_boxes = QAction("Show All Bounding Boxes", self)
        self.action_toggle_boxes.setCheckable(True)
        self.action_toggle_boxes.setChecked(True)
        self.action_toggle_boxes.triggered.connect(self.toggle_bbox_display)
        view_menu.addAction(self.action_toggle_boxes)
        
        # === SETTINGS Menu ===
        settings_menu = menubar.addMenu("⚙️ &Settings")
        
        # Model selection submenu
        model_menu = settings_menu.addMenu("🤖 Model Selection")
        
        # Will be populated dynamically
        self.model_type_actions = []
        for model_type, info in self.available_models.items():
            action = QAction(f"{model_type} - {info['config']['description']}", self)
            action.setData(model_type)
            action.triggered.connect(lambda checked, mt=model_type: self.load_model_from_menu(mt))
            model_menu.addAction(action)
            self.model_type_actions.append(action)
        
        settings_menu.addSeparator()
        
        # Detection parameters submenu
        params_menu = settings_menu.addMenu("📊 Detection Parameters")
        
        # Add image size action
        action_imgsz = QAction("Set Image Size...", self)
        action_imgsz.triggered.connect(self.show_imgsz_dialog)
        params_menu.addAction(action_imgsz)
        
        # Add confidence action
        action_conf = QAction("Set Confidence Threshold...", self)
        action_conf.triggered.connect(self.show_conf_dialog)
        params_menu.addAction(action_conf)
        
        # === LISTS Menu ===
        lists_menu = menubar.addMenu("📋 &Lists")
        
        # Toggle displays
        self.action_toggle_lanes = QAction("✅ Show Lanes", self)
        self.action_toggle_lanes.setCheckable(True)
        self.action_toggle_lanes.setChecked(True)
        self.action_toggle_lanes.triggered.connect(self.toggle_lane_display)
        lists_menu.addAction(self.action_toggle_lanes)
        
        self.action_toggle_rois = QAction("✅ Show Direction ROIs", self)
        self.action_toggle_rois.setCheckable(True)
        self.action_toggle_rois.setChecked(True)
        self.action_toggle_rois.triggered.connect(self.toggle_roi_display)
        lists_menu.addAction(self.action_toggle_rois)
        
        lists_menu.addSeparator()
        
        # Edit items
        action_edit_lane = QAction("Edit Lane...", self)
        action_edit_lane.triggered.connect(self.show_edit_lane_dialog)
        lists_menu.addAction(action_edit_lane)
        
        action_edit_roi = QAction("Edit Direction ROI...", self)
        action_edit_roi.triggered.connect(self.show_edit_roi_dialog)
        lists_menu.addAction(action_edit_roi)
        
        # === DETECTION Menu ===
        detection_menu = menubar.addMenu("🚀 &Detection")
        
        self.action_start_detection = QAction("Start Detection", self)
        self.action_start_detection.setShortcut("Space")
        self.action_start_detection.triggered.connect(self.start_detection)
        detection_menu.addAction(self.action_start_detection)
        
        # === HELP Menu ===
        help_menu = menubar.addMenu("❓ &Help")
        
        action_about = QAction("About", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)
        
        action_shortcuts = QAction("Keyboard Shortcuts", self)
        action_shortcuts.setShortcut("F1")
        action_shortcuts.triggered.connect(self.show_shortcuts)
        help_menu.addAction(action_shortcuts)
    
    def show_about(self):
        '''Show about dialog'''
        QMessageBox.about(
            self,
            "About Traffic Violation by dangdoday",
            "<h2>Traffic Violation Detection System</h2>"
            "<p>Version 2.0 - by dangdoday</p>"
            "<p>Advanced traffic violation detection using YOLOv8</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Lane violation detection</li>"
            "<li>Stopline crossing detection</li>"
            "<li>Traffic light violation (direction-aware)</li>"
            "<li>Multi-direction ROI support</li>"
            "<li>Reference vector for tilted cameras</li>"
            "<li>Auto save/load configuration</li>"
            "</ul>"
        )
    
    def show_shortcuts(self):
        '''Show keyboard shortcuts help'''
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "<h3>Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>Ctrl+O</b></td><td>Open Video</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save Configuration</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Load Configuration</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Exit</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>L</b></td><td>Add Lane</td></tr>"
            "<tr><td><b>S</b></td><td>Set Stop Line</td></tr>"
            "<tr><td><b>T</b></td><td>Add Traffic Light</td></tr>"
            "<tr><td><b>D</b></td><td>Draw Direction ROI</td></tr>"
            "<tr><td><b>R</b></td><td>Set Reference Vector</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Enter</b></td><td>Finish Drawing (Lane/ROI/Ref Vector)</td></tr>"
            "<tr><td><b>E</b></td><td>Edit Direction ROI</td></tr>"
            "<tr><td><b>Return</b></td><td>Finish Editing</td></tr>"
            "<tr><td><b>Delete</b></td><td>Delete Selected</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Space</b></td><td>Start/Stop Detection</td></tr>"
            "<tr><td><b>F1</b></td><td>Show This Help</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Right-Click</b></td><td>Context Menu on Video</td></tr>"
            "</table>"
        )
    
    def load_model_from_menu(self, model_type):
        """Load model when selected from menu"""
        if model_type in self.available_models:
            first_weight = self.available_models[model_type]["weights"][0]
            self.load_model(model_type, first_weight)
            self.statusBar().showMessage(f"Loaded model: {model_type}")
    
    def show_imgsz_dialog(self):
        """Show dialog to set image size"""
        from PyQt5.QtWidgets import QInputDialog
        current_imgsz = self.imgsz_spinbox.value()
        imgsz, ok = QInputDialog.getInt(
            self,
            "Set Image Size",
            "Enter image size (320-1280, multiple of 32):",
            current_imgsz,
            320,
            1280,
            32
        )
        if ok:
            self.imgsz_spinbox.setValue(imgsz)
            self.on_imgsz_changed(imgsz)
            self.statusBar().showMessage(f"Image size set to: {imgsz}")
    
    def show_conf_dialog(self):
        """Show dialog to set confidence threshold"""
        from PyQt5.QtWidgets import QInputDialog
        current_conf = self.conf_spinbox.value()
        conf, ok = QInputDialog.getDouble(
            self,
            "Set Confidence Threshold",
            "Enter confidence threshold (0.1-0.95):",
            current_conf,
            0.1,
            0.95,
            2
        )
        if ok:
            self.conf_spinbox.setValue(conf)
            self.on_conf_changed(conf)
            self.statusBar().showMessage(f"Confidence threshold set to: {conf:.2f}")
    
    def show_lane_list_dialog(self):
        """Show dialog with lane list"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Lane List")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout()
        
        lane_list = QListWidget()
        for idx, lane in enumerate(LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            lane_list.addItem(f"Lane {idx}: {len(lane['poly'])} points - {', '.join(allowed)}")
        
        layout.addWidget(QLabel("<b>Configured Lanes:</b>"))
        layout.addWidget(lane_list)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def show_direction_list_dialog(self):
        """Show dialog with direction ROI list"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Direction ROI List")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        direction_list = QListWidget()
        for idx, roi in enumerate(DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            secondary_dirs = roi.get('secondary_directions', [])
            allowed_dirs = [primary_dir] + [d.upper() for d in secondary_dirs]
            
            # Get traffic light info
            tl_colors = []
            for tl_idx in roi.get('tl_ids', []):
                if tl_idx < len(TL_ROIS):
                    color = TL_ROIS[tl_idx].get('last_color', 'unknown')
                    tl_colors.append(f"TL{tl_idx + 1}:{color}")
            
            tl_info = ' | '.join(tl_colors) if tl_colors else 'No TL'
            points = roi.get('points', [])
            direction_list.addItem(
                f"ROI {idx}: {', '.join(allowed_dirs)} - {len(points)} pts - {tl_info}"
            )
        
        layout.addWidget(QLabel("<b>Configured Direction ROIs:</b>"))
        layout.addWidget(direction_list)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def toggle_lane_display(self):
        """Toggle lane overlay on/off"""
        self.show_lanes = self.action_toggle_lanes.isChecked()
        status = "ON" if self.show_lanes else "OFF"
        print(f"🔵 Lane display: {status}")
        self.status_label.setText(f"Status: Lane display {status}")
    
    def toggle_roi_display(self):
        """Toggle direction ROI overlay on/off"""
        self.show_roi_overlays = self.action_toggle_rois.isChecked()
        status = "ON" if self.show_roi_overlays else "OFF"
        print(f"🔵 Direction ROI display: {status}")
        self.status_label.setText(f"Status: Direction ROI display {status}")
    
    def show_edit_lane_dialog(self):
        """Show dialog to select and edit a lane"""
        global LANE_CONFIGS
        
        if not LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes configured yet. Please add lanes first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Lane")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Lane list
        lane_list = QListWidget()
        for idx, lane in enumerate(LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            points = lane.get('poly', [])
            lane_list.addItem(f"Lane {idx}: {len(points)} points - Allowed: {', '.join(allowed)}")
        
        layout.addWidget(QLabel("<b>Select a lane to edit:</b>"))
        layout.addWidget(lane_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Edit Selected")
        btn_edit.clicked.connect(lambda: self.start_edit_selected_lane(lane_list.currentRow(), dialog))
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(lambda: self.delete_selected_lane(lane_list.currentRow(), dialog))
        btn_layout.addWidget(btn_delete)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def show_edit_roi_dialog(self):
        """Show dialog to select and edit a direction ROI"""
        global DIRECTION_ROIS
        
        if not DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No direction ROIs configured yet. Please add ROIs first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Direction ROI")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # ROI list
        roi_list = QListWidget()
        for idx, roi in enumerate(DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            secondary_dirs = roi.get('secondary_directions', [])
            allowed_dirs = [primary_dir] + [d.upper() for d in secondary_dirs]
            points = roi.get('points', [])
            roi_list.addItem(f"ROI {idx}: {', '.join(allowed_dirs)} - {len(points)} points")
        
        layout.addWidget(QLabel("<b>Select a direction ROI to edit:</b>"))
        layout.addWidget(roi_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Edit Selected")
        btn_edit.clicked.connect(lambda: self.start_edit_selected_roi(roi_list.currentRow(), dialog))
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(lambda: self.delete_selected_roi(roi_list.currentRow(), dialog))
        btn_layout.addWidget(btn_delete)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def start_edit_selected_lane(self, lane_idx, dialog):
        """Start editing the selected lane"""
        global LANE_CONFIGS
        
        if lane_idx < 0 or lane_idx >= len(LANE_CONFIGS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a lane to edit.")
            return
        
        dialog.close()
        
        # Use lane selector to edit
        if hasattr(self, 'lane_selector'):
            from ui.lane_selector import LaneSelector
            lane_editor = LaneSelector(self, edit_mode=True, lane_index=lane_idx)
            lane_editor.exec_()
            print(f"✏️ Editing lane {lane_idx + 1}")
        else:
            QMessageBox.information(self, "Edit Lane", 
                f"Lane {lane_idx + 1} selected for editing.\nUse 'Delete Selected Lane' to remove it, then redraw.")
    
    def start_edit_selected_roi(self, roi_idx, dialog):
        """Start editing the selected direction ROI"""
        global DIRECTION_ROIS
        
        if roi_idx < 0 or roi_idx >= len(DIRECTION_ROIS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a ROI to edit.")
            return
        
        dialog.close()
        
        # Start ROI editor
        self.roi_editor.start_editing(roi_idx)
        self.action_smooth_roi.setEnabled(True)
        self.action_change_directions.setEnabled(True)
        self.action_finish_edit.setEnabled(True)
        
        print(f"✏️ Editing Direction ROI {roi_idx + 1}")
        self.status_label.setText(f"Status: Editing ROI {roi_idx + 1} - Drag points to adjust")
    
    def delete_selected_lane(self, lane_idx, dialog):
        """Delete the selected lane"""
        global LANE_CONFIGS
        
        if lane_idx < 0 or lane_idx >= len(LANE_CONFIGS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a lane to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete Lane {lane_idx + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del LANE_CONFIGS[lane_idx]
            print(f"🗑️ Lane {lane_idx + 1} deleted")
            self.status_label.setText(f"Status: Lane {lane_idx + 1} deleted. Total: {len(LANE_CONFIGS)}")
            dialog.close()
    
    def delete_selected_roi(self, roi_idx, dialog):
        """Delete the selected direction ROI"""
        global DIRECTION_ROIS
        
        if roi_idx < 0 or roi_idx >= len(DIRECTION_ROIS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a ROI to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete Direction ROI {roi_idx + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del DIRECTION_ROIS[roi_idx]
            print(f"🗑️ Direction ROI {roi_idx + 1} deleted")
            self.status_label.setText(f"Status: ROI {roi_idx + 1} deleted. Total: {len(DIRECTION_ROIS)}")
            dialog.close()
    
    def update_lists(self):
        """Placeholder - list widgets removed"""
        pass
            
    def start_detection(self):
        global _detection_running
        if not _detection_running:
            if self.yolo_model is None:
                self.status_label.setText("Status: Model not loaded at startup")
                QMessageBox.warning(self, "No Model", "Please select a model first!")
                return
            
            # Check if reference vector is set (critical for direction detection accuracy)
            if self.ref_vector_p1 is None or self.ref_vector_p2 is None:
                if DIRECTION_ROIS:  # Only warn if direction ROIs exist
                    reply = QMessageBox.question(
                        self,
                        "⚠️ Reference Vector Not Set",
                        "Reference Vector chưa được thiết lập để xác định hướng thẳng.\n\n"
                        "Điều này CÓ THỂ ẢNH HƯỞNG ĐỘ CHÍNH XÁC khi:\n"
                        "- Phát hiện xe rẽ trái/phải\n"
                        "- Xác định vi phạm đèn tín hiệu theo hướng\n\n"
                        "⚠️ Khuyến nghị: Set Reference Vector trước khi start detection\n"
                        "(Click 'Set Reference Vector' và chọn 2 điểm theo hướng thẳng)\n\n"
                        "Bạn có muốn tiếp tục KHÔNG CÓ Reference Vector?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        self.status_label.setText("Status: Please set Reference Vector first")
                        return
            
            # Pass pre-loaded model to thread
            if not self.thread.model_loaded:
                self.thread.set_model(self.yolo_model)
                self.thread.model_config = self.current_model_config
            
            self.thread.detection_enabled = True
            _detection_running = True
            self.btn_start.setText("Stop Detection")
            self.action_start_detection.setText("Stop Detection")
            self.status_label.setText("Status: Detection running...")
            print("🚀 Detection started")
        else:
            self.thread.detection_enabled = False
            _detection_running = False
            self.btn_start.setText("Start Detection")
            self.action_start_detection.setText("Start Detection")
            self.status_label.setText("Status: Detection stopped")
            print("⏹️ Detection stopped")
            VIOLATOR_TRACK_IDS.clear()
            RED_LIGHT_VIOLATORS.clear()
            LANE_VIOLATORS.clear()
            PASSED_VEHICLES.clear()
            MOTORBIKE_COUNT.clear()
            CAR_COUNT.clear()

    def update_tl_colors(self, frame):
        """Update current color for each TL ROI using HSV pixel counting - throttled to every 10 frames"""
        global TL_ROIS
        if not self.tl_tracking_active or not TL_ROIS:
            return
        
        # Only update color every 10 frames for performance
        self.tl_color_frame_count += 1
        if self.tl_color_frame_count < 10:
            return
        self.tl_color_frame_count = 0
        
        updated_rois = []
        
        for i, roi_data in enumerate(TL_ROIS):
            x1, y1, x2, y2, tl_type, _ = roi_data
            roi = frame[y1:y2, x1:x2]
            
            if roi.size > 0:
                # Detect current color using HSV
                current_color = self._detect_color_hsv(roi)
                updated_rois.append((x1, y1, x2, y2, tl_type, current_color))
            else:
                updated_rois.append(roi_data)
        
        TL_ROIS = updated_rois
    
    def _detect_color_hsv(self, roi):
        """Detect traffic light color using HSV pixel counting"""
        try:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Define HSV ranges for red, yellow, green
            # Red (two ranges due to hue wraparound)
            red_lower1 = np.array([0, 100, 100])
            red_upper1 = np.array([10, 255, 255])
            red_lower2 = np.array([170, 100, 100])
            red_upper2 = np.array([180, 255, 255])
            
            # Yellow
            yellow_lower = np.array([20, 100, 100])
            yellow_upper = np.array([30, 255, 255])
            
            # Green
            green_lower = np.array([40, 50, 50])
            green_upper = np.array([90, 255, 255])
            
            # Count pixels
            red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
            red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
            red_count = cv2.countNonZero(red_mask1) + cv2.countNonZero(red_mask2)
            
            yellow_count = cv2.countNonZero(cv2.inRange(hsv, yellow_lower, yellow_upper))
            green_count = cv2.countNonZero(cv2.inRange(hsv, green_lower, green_upper))
            
            # Return color with most pixels
            counts = {'đỏ': red_count, 'vàng': yellow_count, 'xanh': green_count}
            max_color = max(counts, key=counts.get)
            
            # Only return if significant pixels detected
            if counts[max_color] > roi.size * 0.01:  # At least 1% of ROI
                return max_color
            return 'unknown'
            
        except Exception as e:
            return 'unknown'
    
    def find_tl_roi(self):
        """Manual TL ROI selection - click 2 points on video"""
        global _drawing_mode, _tmp_tl_point
        if self.current_frame is None:
            self.status_label.setText("Status: No frame to select ROI from")
            return
        
        _drawing_mode = 'tl_manual'
        _tmp_tl_point = None
        self.status_label.setText("Status: Click 2 points to draw TL ROI")
        print("🖊️ Manual TL ROI mode - click 2 points")
        self.btn_find_tl.setText("[Selecting...] Cancel")
        self.btn_find_tl.clicked.disconnect()
        self.btn_find_tl.clicked.connect(self.cancel_tl_selection)
    
    def cancel_tl_selection(self):
        """Cancel manual TL selection"""
        global _drawing_mode, _tmp_tl_point
        _drawing_mode = None
        _tmp_tl_point = None
        self.status_label.setText("Status: TL selection cancelled")
        self.btn_find_tl.setText("Add Traffic Light (Draw ROI)")
        self.btn_find_tl.clicked.disconnect()
        self.btn_find_tl.clicked.connect(self.find_tl_roi)
    
    def delete_tl(self):
        """Delete selected traffic light ROI"""
        global TL_ROIS
        if len(TL_ROIS) == 0:
            self.status_label.setText("Status: No traffic lights to delete")
            QMessageBox.information(self, "No Traffic Lights", "No traffic lights to delete.")
            return
        
        # Show list of TLs to delete
        tl_names = [f"TL {i+1} [{tl_type}]: Position ({x1},{y1},{x2},{y2})" 
                    for i, (x1, y1, x2, y2, tl_type, _) in enumerate(TL_ROIS)]
        tl_name, ok = QInputDialog.getItem(
            self,
            "Delete Traffic Light",
            "Select traffic light to delete:",
            tl_names,
            editable=False
        )
        
        if ok and tl_name:
            tl_idx = tl_names.index(tl_name)
            deleted_tl = TL_ROIS.pop(tl_idx)
            print(f"🗑️ Deleted TL {tl_idx+1}: {deleted_tl}")
            self.status_label.setText(f"Status: Deleted TL {tl_idx+1}. {len(TL_ROIS)} TL(s) remaining.")
            
            # If no TLs left, disable tracking
            if len(TL_ROIS) == 0:
                self.tl_tracking_active = False
                print("⏹️ No TLs remaining, color tracking disabled")
    
    # ========================================================================
    # Direction ROI Management Methods
    # ========================================================================
    
    def on_direction_changed(self, direction):
        """Called when user selects direction from dropdown"""
        global _selected_direction
        _selected_direction = direction
        print(f"🎯 Selected direction: {direction.upper()}")
        self.status_label.setText(f"Status: Direction set to {direction.upper()}")
    
    def start_add_direction_roi(self):
        """Start drawing direction ROI"""
        global _drawing_mode, _tmp_direction_roi_pts
        
        if self.current_frame is None:
            QMessageBox.warning(self, "No Frame", "No video frame available. Please load a video first.")
            return
        
        _drawing_mode = 'direction_roi'
        _tmp_direction_roi_pts = []
        self.btn_finish_direction_roi.setEnabled(True)
        self.status_label.setText(f"Status: Click points to draw {_selected_direction.upper()} ROI. Click 'Finish' or press ENTER when done.")
        print(f"🖊️ Drawing Direction ROI: {_selected_direction.upper()}")
    
    def finish_direction_roi(self):
        """Finish drawing current direction ROI"""
        global _drawing_mode, _tmp_direction_roi_pts, _selected_direction, DIRECTION_ROIS
        
        if len(_tmp_direction_roi_pts) < 3:
            QMessageBox.warning(self, "Invalid ROI", "Direction ROI needs at least 3 points!")
            return
        
        # Ask user to select allowed directions (multiple choice)
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Allowed Directions")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Chọn các hướng đi được phép trong vùng này:"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        # Default: select primary direction
        if _selected_direction == 'left':
            check_left.setChecked(True)
        elif _selected_direction == 'straight':
            check_straight.setChecked(True)
        elif _selected_direction == 'right':
            check_right.setChecked(True)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("\nHướng chính (Primary - for display):"))
        
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left")
        radio_straight = QRadioButton("⬆️ Straight")
        radio_right = QRadioButton("➡️ Right")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if _selected_direction == 'left':
            radio_left.setChecked(True)
        elif _selected_direction == 'straight':
            radio_straight.setChecked(True)
        elif _selected_direction == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Get allowed directions
        allowed_dirs = []
        if check_left.isChecked():
            allowed_dirs.append('left')
        if check_straight.isChecked():
            allowed_dirs.append('straight')
        if check_right.isChecked():
            allowed_dirs.append('right')
        
        if not allowed_dirs:
            QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return
        
        # Get primary direction
        if radio_left.isChecked():
            primary_dir = 'left'
        elif radio_straight.isChecked():
            primary_dir = 'straight'
        elif radio_right.isChecked():
            primary_dir = 'right'
        else:
            primary_dir = allowed_dirs[0]
        
        # Create ROI
        roi_num = len(DIRECTION_ROIS) + 1
        new_roi = {
            'name': f'roi_{roi_num}',
            'points': _tmp_direction_roi_pts.copy(),
            'allowed_directions': allowed_dirs,
            'primary_direction': primary_dir,
            # Backward compat
            'direction': primary_dir
        }
        
        DIRECTION_ROIS.append(new_roi)
        
        allowed_str = '+'.join([d.upper() for d in allowed_dirs])
        print(f"✅ Created Direction ROI #{roi_num}: {allowed_str} (primary: {primary_dir.upper()}, {len(_tmp_direction_roi_pts)} points)")
        self.status_label.setText(f"Status: Added ROI #{roi_num} - Allowed: {allowed_str}")
        
        # Reset
        _drawing_mode = None
        _tmp_direction_roi_pts = []
        self.btn_finish_direction_roi.setEnabled(False)
    
    def update_direction_roi_list(self):
        """Update direction ROI list widget"""
        self.direction_roi_list.clear()
        for i, roi in enumerate(DIRECTION_ROIS):
            # Handle both old format (direction) and new format (allowed_directions)
            if 'allowed_directions' in roi:
                allowed = roi['allowed_directions']
                primary = roi.get('primary_direction', allowed[0])
                
                # Icons for display
                icons = []
                if 'left' in allowed:
                    icons.append('⬅️')
                if 'straight' in allowed:
                    icons.append('⬆️')
                if 'right' in allowed:
                    icons.append('➡️')
                
                icon_str = ''.join(icons)
                allowed_str = '+'.join([d[0].upper() for d in allowed])  # L+S+R
                
                self.direction_roi_list.addItem(f"{icon_str} ROI {i+1}: {allowed_str} (primary: {primary[0].upper()}, {len(roi['points'])} pts)")
            else:
                # Backward compatibility - old format
                direction = roi.get('direction', 'straight')
                direction_upper = direction.upper()
                color_mark = "🔴" if direction == 'left' else "🟢" if direction == 'straight' else "🟡"
                self.direction_roi_list.addItem(f"{color_mark} ROI {i+1}: {direction_upper} ({len(roi['points'])} pts)")
    
    def delete_direction_roi(self):
        """Delete selected direction ROI - shows selection dialog"""
        global DIRECTION_ROIS
        
        if not DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No direction ROIs to delete!")
            return
        
        # Show selection dialog
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout
        
        selection_dialog = QDialog(self)
        selection_dialog.setWindowTitle("Select Direction ROI to Delete")
        sel_layout = QVBoxLayout(selection_dialog)
        
        sel_roi_list = QListWidget()
        for idx, roi in enumerate(DIRECTION_ROIS):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            allowed = roi.get('allowed_directions', [primary_dir.lower()])
            allowed_str = '+'.join([d.upper() for d in allowed])
            sel_roi_list.addItem(f"ROI {idx+1}: {allowed_str} - {len(roi['points'])} points")
        
        sel_layout.addWidget(QLabel("Select a direction ROI to delete:"))
        sel_layout.addWidget(sel_roi_list)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Delete")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        sel_layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(selection_dialog.reject)
        
        def on_ok():
            sel_idx = sel_roi_list.currentRow()
            if sel_idx >= 0:
                selection_dialog.selected_idx = sel_idx
                selection_dialog.accept()
            else:
                QMessageBox.warning(selection_dialog, "No Selection", "Please select a direction ROI!")
        
        btn_ok.clicked.connect(on_ok)
        
        if selection_dialog.exec_() == QDialog.Rejected:
            return
        
        selected_idx = getattr(selection_dialog, 'selected_idx', -1)
        if selected_idx >= 0 and selected_idx < len(DIRECTION_ROIS):
            deleted_roi = DIRECTION_ROIS.pop(selected_idx)
            print(f"🗑️ Deleted Direction ROI {selected_idx+1}")
            self.status_label.setText(f"Status: Deleted Direction ROI {selected_idx+1}")
    
    def start_edit_direction_roi(self):
        """Start editing selected direction ROI - always shows selection dialog"""
        global DIRECTION_ROIS
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
        
        # Check if ROIs exist
        if not DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No direction ROIs configured yet. Please add ROIs first.")
            return
        
        # Always show selection dialog
        selection_dialog = QDialog(self)
        selection_dialog.setWindowTitle("Select Direction ROI to Edit")
        selection_dialog.setMinimumSize(400, 300)
        sel_layout = QVBoxLayout(selection_dialog)
        
        sel_layout.addWidget(QLabel("<b>Select a direction ROI to edit:</b>"))
        sel_roi_list = QListWidget()
        for idx, roi in enumerate(DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            allowed = roi.get('allowed_directions', [primary_dir.lower()])
            allowed_str = '+'.join([d.upper() for d in allowed])
            points = roi.get('points', [])
            sel_roi_list.addItem(f"ROI {idx}: {allowed_str} - {len(points)} points")
        sel_layout.addWidget(sel_roi_list)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Edit")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        sel_layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(selection_dialog.reject)
        
        def on_ok():
            sel_idx = sel_roi_list.currentRow()
            if sel_idx >= 0:
                selection_dialog.selected_idx = sel_idx
                selection_dialog.accept()
            else:
                QMessageBox.warning(selection_dialog, "No Selection", "Please select a ROI!")
        
        btn_ok.clicked.connect(on_ok)
        
        if selection_dialog.exec_() == QDialog.Rejected:
            return
        
        selected_idx = getattr(selection_dialog, 'selected_idx', -1)
        if selected_idx < 0:
            return
        
        # Start editing mode
        self.roi_editor.start_editing(selected_idx)
        
        # Update UI
        self.btn_finish_edit_roi.setEnabled(True)
        self.btn_smooth_roi.setEnabled(True)
        self.btn_change_roi_direction.setEnabled(True)
        self.btn_edit_direction_roi.setEnabled(False)
        
        # Update menu actions
        self.action_finish_edit.setEnabled(True)
        self.action_smooth_roi.setEnabled(True)
        self.action_change_directions.setEnabled(True)
        
        # Disable other drawing buttons
        self.btn_add_direction_roi.setEnabled(False)
        self.btn_delete_direction_roi.setEnabled(False)
        
        roi = DIRECTION_ROIS[selected_idx]
        dir_display = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
        self.status_label.setText(f"Status: Editing {dir_display} ROI - {len(roi['points'])} points | "
                                 "Left-click+drag=move | Double-click=add | Right-click=delete")
        
        print(f"✏️ Editing Direction ROI {selected_idx}: {dir_display} ({len(roi['points'])} points)")
        print(f"   Left-click and drag to move points")
        print(f"   Double-click on edge to add new point")
        print(f"   Right-click on point to delete (min 3 points)")
        print(f"   Use 'Change ROI Directions' to modify allowed directions")
    
    def finish_edit_roi(self):
        """Finish editing current ROI and show direction selection dialog"""
        if not self.roi_editor.is_editing():
            return
        
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QLabel, QRadioButton, QButtonGroup
        
        roi_idx = self.roi_editor.editing_roi_index
        roi = DIRECTION_ROIS[roi_idx]
        
        # Finish editing
        self.roi_editor.finish_editing()
        
        # Update UI
        self.btn_finish_edit_roi.setEnabled(False)
        self.btn_smooth_roi.setEnabled(False)
        self.btn_change_roi_direction.setEnabled(False)
        self.btn_edit_direction_roi.setEnabled(True)
        self.btn_add_direction_roi.setEnabled(True)
        self.btn_delete_direction_roi.setEnabled(True)
        
        # Update menu actions
        self.action_finish_edit.setEnabled(False)
        self.action_smooth_roi.setEnabled(False)
        self.action_change_directions.setEnabled(False)
        
        # Show direction selection dialog
        current_allowed = roi.get('allowed_directions', [roi.get('direction', 'straight')])
        current_primary = roi.get('primary_direction', roi.get('direction', 'straight'))
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Configure ROI {roi_idx + 1}")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<b>Chọn các hướng đi được phép:</b>"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        # Set current values
        check_left.setChecked('left' in current_allowed)
        check_straight.setChecked('straight' in current_allowed)
        check_right.setChecked('right' in current_allowed)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("<br><b>Hướng chính</b> (Primary - for display color):"))
        
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left (Red 🔴)")
        radio_straight = QRadioButton("⬆️ Straight (Green 🟢)")
        radio_right = QRadioButton("➡️ Right (Yellow 🟡)")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if current_primary == 'left':
            radio_left.setChecked(True)
        elif current_primary == 'straight':
            radio_straight.setChecked(True)
        elif current_primary == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # Get new settings
            new_allowed = []
            if check_left.isChecked():
                new_allowed.append('left')
            if check_straight.isChecked():
                new_allowed.append('straight')
            if check_right.isChecked():
                new_allowed.append('right')
            
            if not new_allowed:
                QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
                new_allowed = ['straight']  # Default to straight
            
            # Get new primary
            if radio_left.isChecked():
                new_primary = 'left'
            elif radio_straight.isChecked():
                new_primary = 'straight'
            elif radio_right.isChecked():
                new_primary = 'right'
            else:
                new_primary = new_allowed[0]
            
            # Update ROI
            roi['allowed_directions'] = new_allowed
            roi['primary_direction'] = new_primary
            roi['direction'] = new_primary  # Backward compat
            
            allowed_str = '+'.join([d.upper() for d in new_allowed])
            print(f"✅ Finished editing ROI {roi_idx + 1}: {allowed_str} (primary: {new_primary.upper()})")
            self.status_label.setText(f"Status: ROI {roi_idx + 1} - {allowed_str}")
        else:
            dir_display = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            self.status_label.setText(f"Status: Finished editing {dir_display} ROI - {len(roi['points'])} points")
            print(f"✅ Finished editing ROI {roi_idx}: {len(roi['points'])} points")
    
    def smooth_current_roi(self):
        """Smooth the currently editing ROI"""
        if not self.roi_editor.is_editing():
            return
        
        roi_idx = self.roi_editor.editing_roi_index
        roi = DIRECTION_ROIS[roi_idx]
        
        old_count = len(roi['points'])
        
        # Ask for smoothing level
        epsilon, ok = QInputDialog.getDouble(
            self,
            "Smooth ROI",
            "Epsilon factor (0.005-0.05):\nLower = more detail, Higher = fewer points",
            0.01,  # default
            0.001,  # min
            0.1,  # max
            3  # decimals
        )
        
        if not ok:
            return
        
        # Apply smoothing
        roi['points'] = self.roi_editor.smooth_roi(roi['points'], epsilon_factor=epsilon)
        
        new_count = len(roi['points'])
        self.status_label.setText(f"Status: Smoothed ROI - {old_count} → {new_count} points")
        print(f"🔧 Smoothed ROI: {old_count} → {new_count} points (epsilon={epsilon})")
    
    def change_roi_directions(self):
        """Change allowed directions for currently editing ROI"""
        if not self.roi_editor.is_editing():
            QMessageBox.warning(self, "Not Editing", "Please start editing a ROI first!")
            return
        
        roi_idx = self.roi_editor.editing_roi_index
        roi = DIRECTION_ROIS[roi_idx]
        
        # Get current settings
        current_allowed = roi.get('allowed_directions', [roi.get('direction', 'straight')])
        current_primary = roi.get('primary_direction', roi.get('direction', 'straight'))
        
        # Dialog to change directions
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QLabel, QRadioButton, QButtonGroup
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Change ROI {roi_idx + 1} Directions")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(f"<b>ROI #{roi_idx + 1}</b><br>Chọn các hướng đi được phép:"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        # Set current values
        check_left.setChecked('left' in current_allowed)
        check_straight.setChecked('straight' in current_allowed)
        check_right.setChecked('right' in current_allowed)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("<br><b>Hướng chính</b> (Primary - for display color):"))
        
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left (Red 🔴)")
        radio_straight = QRadioButton("⬆️ Straight (Green 🟢)")
        radio_right = QRadioButton("➡️ Right (Yellow 🟡)")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if current_primary == 'left':
            radio_left.setChecked(True)
        elif current_primary == 'straight':
            radio_straight.setChecked(True)
        elif current_primary == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Get new settings
        new_allowed = []
        if check_left.isChecked():
            new_allowed.append('left')
        if check_straight.isChecked():
            new_allowed.append('straight')
        if check_right.isChecked():
            new_allowed.append('right')
        
        if not new_allowed:
            QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return
        
        # Get new primary
        if radio_left.isChecked():
            new_primary = 'left'
        elif radio_straight.isChecked():
            new_primary = 'straight'
        elif radio_right.isChecked():
            new_primary = 'right'
        else:
            new_primary = new_allowed[0]
        
        # Update ROI
        roi['allowed_directions'] = new_allowed
        roi['primary_direction'] = new_primary
        roi['direction'] = new_primary  # Backward compat
        
        allowed_str = '+'.join([d.upper() for d in new_allowed])
        print(f"🔄 Changed ROI {roi_idx + 1} directions: {allowed_str} (primary: {new_primary.upper()})")
        self.status_label.setText(f"Status: ROI {roi_idx + 1} - Allowed: {allowed_str}")
    
    def save_direction_rois(self):
        """Save direction ROIs to JSON file"""
        import json
        from pathlib import Path
        
        if not DIRECTION_ROIS:
            QMessageBox.warning(self, "No ROIs", "No Direction ROIs to save!")
            return
        
        # Default filename
        video_name = Path(self.video_path).stem
        default_name = f"{video_name}_direction_rois.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Direction ROIs",
            default_name,
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            data = {
                'video': Path(self.video_path).name,
                'frame_shape': list(self.current_frame.shape[:2]) if self.current_frame is not None else [0, 0],
                'rois': DIRECTION_ROIS
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Saved {len(DIRECTION_ROIS)} Direction ROIs to: {file_path}")
            self.status_label.setText(f"Status: Saved {len(DIRECTION_ROIS)} ROIs to JSON")
            QMessageBox.information(self, "Saved", f"Saved {len(DIRECTION_ROIS)} Direction ROIs successfully!")
    
    def load_direction_rois(self):
        """Load direction ROIs from JSON file"""
        import json
        global DIRECTION_ROIS
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Direction ROIs",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                DIRECTION_ROIS = data.get('rois', [])
                
                print(f"📂 Loaded {len(DIRECTION_ROIS)} Direction ROIs from: {file_path}")
                self.status_label.setText(f"Status: Loaded {len(DIRECTION_ROIS)} ROIs")
                
                QMessageBox.information(self, "Loaded", f"Loaded {len(DIRECTION_ROIS)} Direction ROIs successfully!")
                
            except Exception as e:
                print(f"❌ Error loading ROIs: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load ROIs: {e}")
    
    def toggle_direction_rois(self):
        """Toggle showing direction ROIs on video"""
        # Get state from whichever control was triggered
        sender = self.sender()
        if isinstance(sender, QAction):
            # Triggered from menu - update button
            self.show_direction_rois = sender.isChecked()
            self.btn_toggle_direction_rois.setChecked(self.show_direction_rois)
        else:
            # Triggered from button - update menu
            self.show_direction_rois = self.btn_toggle_direction_rois.isChecked()
            self.action_toggle_direction_rois.setChecked(self.show_direction_rois)
        
        if self.show_direction_rois:
            self.btn_toggle_direction_rois.setText("Show Direction ROIs: ON")
            print("👁️ Direction ROIs visible")
        else:
            self.btn_toggle_direction_rois.setText("Show Direction ROIs: OFF")
            print("🙈 Direction ROIs hidden")
    
    # ========================================================================
    # Reference Vector Management (for camera nghiêng)
    # ========================================================================
    
    def start_set_reference_vector(self):
        """Bắt đầu vẽ reference vector"""
        global _drawing_mode
        
        if self.current_frame is None:
            QMessageBox.warning(self, "No Frame", "No video frame available.")
            return
        
        _drawing_mode = 'ref_vector'
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        self.btn_finish_ref_vector.setEnabled(True)
        self.status_label.setText("Status: Click 2 points on STRAIGHT lane (start → end)")
        print("🧭 Setting Reference Vector: Click 2 points on straight lane")
    
    def finish_reference_vector(self):
        """Hoàn thành reference vector"""
        global _drawing_mode
        
        if self.ref_vector_p1 is None or self.ref_vector_p2 is None:
            QMessageBox.warning(self, "Incomplete", "Need 2 points for reference vector!")
            return
        
        # Tính vector và góc
        dx = self.ref_vector_p2[0] - self.ref_vector_p1[0]
        dy = self.ref_vector_p2[1] - self.ref_vector_p1[1]
        length = math.sqrt(dx**2 + dy**2)
        
        if length < 10:
            QMessageBox.warning(self, "Too Short", "Reference vector too short! Choose points farther apart.")
            return
        
        angle = math.degrees(math.atan2(dy, dx))
        
        # Cập nhật label
        self.ref_vector_label.setText(f"Ref Vector: {angle:.1f}° ({dx:.0f}, {dy:.0f})")
        
        print(f"✅ Reference Vector Set:")
        print(f"   Point 1: {self.ref_vector_p1}")
        print(f"   Point 2: {self.ref_vector_p2}")
        print(f"   Vector: ({dx:.1f}, {dy:.1f})")
        print(f"   Angle: {angle:.2f}°")
        
        # ⚠️ CRITICAL: Update VehicleTracker with reference angle
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.set_reference_angle(angle)
            print(f"🎯 Applied ref_angle={angle:.1f}° to VehicleTracker")
        else:
            print(f"⚠️ Warning: VideoThread not initialized yet, ref_angle will be applied when video loads")
        
        _drawing_mode = None
        self.btn_finish_ref_vector.setEnabled(False)
        self.status_label.setText(f"Status: Reference vector set ({angle:.1f}°)")
        
        QMessageBox.information(self, "Reference Vector Set", 
                               f"Reference vector set successfully!\n\n"
                               f"Angle: {angle:.1f}°\n"
                               f"This will be used to calculate vehicle turning directions\n"
                               f"relative to the straight road direction.")
    
    # ========================================================================
    # End Reference Vector Management
    # ========================================================================
    
    def toggle_bbox_display(self):
        global _show_all_boxes
        # Get state from whichever control was triggered
        sender = self.sender()
        if isinstance(sender, QAction):
            # Triggered from menu - update button
            _show_all_boxes = sender.isChecked()
            self.btn_toggle_bb.setChecked(_show_all_boxes)
        else:
            # Triggered from button - update menu
            _show_all_boxes = self.btn_toggle_bb.isChecked()
            self.action_toggle_boxes.setChecked(_show_all_boxes)
        
        if _show_all_boxes:
            self.btn_toggle_bb.setText("Show All Boxes: ON")
            self.statusBar().showMessage("Status: Showing all vehicles")
            print("📦 Showing ALL vehicle bounding boxes")
        else:
            self.btn_toggle_bb.setText("Show Only Violators: ON")
            self.statusBar().showMessage("Status: Showing only violators")
            print("🚨 Showing ONLY violator bounding boxes")
    
    def select_video(self):
        global _detection_running, VIOLATOR_TRACK_IDS, RED_LIGHT_VIOLATORS, LANE_VIOLATORS, PASSED_VEHICLES, MOTORBIKE_COUNT, CAR_COUNT
        global ALLOWED_VEHICLE_IDS, VEHICLE_CLASSES, LANE_CONFIGS, TL_ROIS, _show_all_boxes
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)"
        )
        
        if file_path:
            # Stop current thread
            self.thread.stop()
            
            # Start new thread with selected video
            self.video_path = file_path
            self.thread = VideoThread(self.video_path)
            self.thread.change_pixmap_signal.connect(self.update_image)
            self.thread.error_signal.connect(self.show_error)
            
            # Pass globals reference to thread
            # Use lambda for _show_all_boxes to get real-time value
            self.thread.set_globals_reference({
                'ALLOWED_VEHICLE_IDS': ALLOWED_VEHICLE_IDS,
                'VEHICLE_CLASSES': VEHICLE_CLASSES,
                'LANE_CONFIGS': LANE_CONFIGS,
                'TL_ROIS': TL_ROIS,
                'DIRECTION_ROIS': DIRECTION_ROIS,
                'get_show_all_boxes': lambda: globals()['_show_all_boxes'],
                'is_on_stop_line': is_on_stop_line,
                'has_crossed_stopline': has_crossed_stopline,
                'check_tl_violation': check_tl_violation,
                'point_in_polygon': point_in_polygon,
                'VIOLATOR_TRACK_IDS': VIOLATOR_TRACK_IDS,
                'RED_LIGHT_VIOLATORS': RED_LIGHT_VIOLATORS,
                'LANE_VIOLATORS': LANE_VIOLATORS,
                'PASSED_VEHICLES': PASSED_VEHICLES,
                'MOTORBIKE_COUNT': MOTORBIKE_COUNT,
                'CAR_COUNT': CAR_COUNT
            })
            
            self.thread.start()
            
            # Store cap for TL detection
            self.cap = cv2.VideoCapture(self.video_path)
            
            self.status_label.setText(f"Status: Loaded {file_path.split('/')[-1]}")
            print(f"📹 Loaded video: {file_path}")
            
            # Reset detection state
            _detection_running = False
            VIOLATOR_TRACK_IDS.clear()
            RED_LIGHT_VIOLATORS.clear()
            LANE_VIOLATORS.clear()
            PASSED_VEHICLES.clear()
            self.btn_start.setText("Start Detection")
            
            # Try to auto-load configuration for this video
            if self.config_manager.config_exists(file_path):
                print(f"🔍 Found existing configuration for this video")
                if self.auto_load_configuration():
                    self.config_status_label.setText(f"✅ Config: Auto-loaded from file")
                    self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                    self.status_label.setText(f"Status: Loaded {file_path.split('/')[-1]} [Config auto-loaded]")
                    return
            
            # No config found - reset ROIs for new video
            TL_ROIS.clear()
            LANE_CONFIGS.clear()
            DIRECTION_ROIS.clear()
            self.ref_vector_p1 = None
            self.ref_vector_p2 = None
            self.ref_vector_label.setText("Ref Vector: Not set")
            self.tl_tracking_active = False
            self.config_status_label.setText("Config: No saved config found")
            self.config_status_label.setStyleSheet("QLabel { color: orange; font-style: italic; }")
            print("♻️ All ROIs reset. Draw new configuration or load from file.")
    
    def load_model(self, model_type, weight_name):
        """Load model dynamically based on selection"""
        if not YOLO_AVAILABLE:
            print("⚠️ YOLO not available")
            return False
        
        try:
            print(f"🔄 Loading {model_type} model: {weight_name}...")
            weight_path = get_weight_path(model_type, weight_name)
            self.yolo_model = YOLO(weight_path)
            self.current_model_type = model_type
            self.current_model_config = get_model_config(model_type)
            
            # Update thread model if thread exists and was already initialized
            if hasattr(self, 'thread') and hasattr(self.thread, 'model_loaded'):
                if self.thread.model_loaded:
                    self.thread.set_model(self.yolo_model)
                    self.thread.model_config = self.current_model_config
            
            # Update spinboxes with model's default values
            if hasattr(self, 'imgsz_spinbox'):
                self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
            if hasattr(self, 'conf_spinbox'):
                self.conf_spinbox.setValue(self.current_model_config['default_conf'])
            
            print(f"✅ Model loaded: {weight_path}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Status: Loaded {model_type} - {weight_name}")
            return True
        except Exception as e:
            import traceback
            print(f"❌ Failed to load model: {e}")
            print(traceback.format_exc())
            if hasattr(self, 'status_label'):
                QMessageBox.warning(self, "Model Load Error", f"Could not load model:\n{e}")
            return False
    
    def update_weight_combo(self):
        """Update weight dropdown based on selected model type"""
        self.weight_combo.clear()
        
        if not self.available_models:
            return
        
        # Get current model type from combo
        current_idx = self.model_type_combo.currentIndex()
        if current_idx < 0:
            return
        
        model_type = list(self.available_models.keys())[current_idx]
        weights = self.available_models[model_type]["weights"]
        
        for weight in weights:
            self.weight_combo.addItem(weight)
    
    def update_model_info_label(self):
        """Update model info label with current config"""
        if self.current_model_config:
            # Get values from spinboxes if they exist
            imgsz = self.imgsz_spinbox.value() if hasattr(self, 'imgsz_spinbox') else self.current_model_config['default_imgsz']
            conf = self.conf_spinbox.value() if hasattr(self, 'conf_spinbox') else self.current_model_config['default_conf']
            info = f"Using: ImgSize={imgsz} | Conf={conf}"
            self.model_info_label.setText(info)
        else:
            self.model_info_label.setText("No model loaded")
    
    def on_model_type_changed(self):
        """Handle model type selection change"""
        self.update_weight_combo()
        
        # Auto-load first weight of new model type
        if self.weight_combo.count() > 0:
            self.on_weight_changed()
    
    def on_weight_changed(self):
        """Handle weight selection change"""
        if self.weight_combo.currentIndex() < 0:
            return
        
        current_idx = self.model_type_combo.currentIndex()
        if current_idx < 0:
            return
        
        model_type = list(self.available_models.keys())[current_idx]
        weight_name = self.weight_combo.currentText()
        
        if weight_name:
            success = self.load_model(model_type, weight_name)
            if success:
                # Update spinboxes with model default values
                if self.current_model_config:
                    self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
                    self.conf_spinbox.setValue(self.current_model_config['default_conf'])
                self.update_model_info_label()
    
    def on_imgsz_changed(self):
        """Handle image size change"""
        new_imgsz = self.imgsz_spinbox.value()
        print(f"📐 ImgSize changed to: {new_imgsz}")
        
        # Update current config
        if self.current_model_config:
            self.current_model_config['default_imgsz'] = new_imgsz
        
        # Update thread config if running
        if hasattr(self, 'thread') and self.thread.model_config:
            self.thread.model_config['default_imgsz'] = new_imgsz
            print(f"✅ Thread ImgSize updated to: {new_imgsz}")
        
        self.update_model_info_label()
    
    def on_conf_changed(self):
        """Handle confidence threshold change"""
        new_conf = round(self.conf_spinbox.value(), 2)  # Round to 2 decimals
        print(f"🎯 Confidence changed to: {new_conf}")
        
        # Update current config
        if self.current_model_config:
            self.current_model_config['default_conf'] = new_conf
        
        # Update thread config if running
        if hasattr(self, 'thread') and self.thread.model_config:
            self.thread.model_config['default_conf'] = new_conf
            print(f"✅ Thread Confidence updated to: {new_conf}")
        
        self.update_model_info_label()
    
    def save_configuration(self):
        """Save all ROI configurations to file"""
        global LANE_CONFIGS, STOP_LINE, TL_ROIS, DIRECTION_ROIS
        
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first before saving configuration.")
            return
        
        try:
            # Convert reference vector to tuple format if set
            ref_vector = None
            if self.ref_vector_p1 and self.ref_vector_p2:
                ref_vector = (tuple(self.ref_vector_p1), tuple(self.ref_vector_p2))
            
            # Debug print
            print(f"🔍 Saving config for video: {self.video_path}")
            print(f"  - Lanes: {len(LANE_CONFIGS)}")
            print(f"  - Stopline: {STOP_LINE}")
            print(f"  - Traffic Lights: {len(TL_ROIS)}")
            print(f"  - Direction ROIs: {len(DIRECTION_ROIS)}")
            print(f"  - Ref Vector: {ref_vector}")
            
            # Save using ConfigManager
            success = self.config_manager.save_config(
                video_path=self.video_path,
                lane_configs=LANE_CONFIGS,
                stop_line=STOP_LINE,
                tl_rois=TL_ROIS,
                direction_rois=DIRECTION_ROIS,
                reference_vector=ref_vector
            )
            
            if success:
                config_path = self.config_manager.get_config_path(self.video_path)
                QMessageBox.information(
                    self, 
                    "Configuration Saved", 
                    f"✅ All ROIs saved successfully!\n\nFile: {config_path.name}\n\n"
                    f"- Lanes: {len(LANE_CONFIGS)}\n"
                    f"- Stopline: {'Yes' if STOP_LINE else 'No'}\n"
                    f"- Traffic Lights: {len(TL_ROIS)}\n"
                    f"- Direction Zones: {len(DIRECTION_ROIS)}\n"
                    f"- Reference Vector: {'Yes' if ref_vector else 'No'}"
                )
                self.config_status_label.setText(f"✅ Config: Saved to file")
                self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            else:
                QMessageBox.critical(self, "Save Failed", "❌ Failed to save configuration. Check console for errors.")
        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Error saving configuration:")
            print(error_details)
            QMessageBox.critical(
                self, 
                "Save Error", 
                f"❌ An error occurred while saving:\n\n{str(e)}\n\nCheck console for details."
            )
    
    def load_configuration(self):
        """Manually load configuration from file"""
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first before loading configuration.")
            return
        
        result = self.config_manager.load_config(self.video_path)
        
        if result is None:
            QMessageBox.warning(
                self, 
                "No Configuration", 
                "No saved configuration found for this video.\n\n"
                "Draw ROIs manually and save them for future use."
            )
            return
        
        self._apply_loaded_config(result)
        
        config_path = self.config_manager.get_config_path(self.video_path)
        QMessageBox.information(
            self, 
            "Configuration Loaded", 
            f"✅ Configuration loaded successfully!\n\nFile: {config_path.name}\n\n"
            f"- Lanes: {len(result['lanes'])}\n"
            f"- Stopline: {'Yes' if result['stopline'] else 'No'}\n"
            f"- Traffic Lights: {len(result['traffic_lights'])}\n"
            f"- Direction Zones: {len(result['direction_zones'])}\n"
            f"- Reference Vector: {'Yes' if result['reference_vector'] else 'No'}"
        )
        
        self.config_status_label.setText(f"✅ Config: Loaded from file")
        self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
    
    def auto_load_configuration(self):
        """Auto-load configuration without showing message box"""
        result = self.config_manager.load_config(self.video_path)
        
        if result is None:
            return False
        
        self._apply_loaded_config(result)
        return True
    
    def _apply_loaded_config(self, config):
        """Apply loaded configuration to global variables and UI"""
        global LANE_CONFIGS, STOP_LINE, TL_ROIS, DIRECTION_ROIS
        
        # Load lanes
        LANE_CONFIGS.clear()
        for lane_data in config['lanes']:
            # Support both 'poly' and 'points' keys for backward compatibility
            points = lane_data.get('poly', lane_data.get('points', []))
            LANE_CONFIGS.append({
                'poly': points,
                'label': lane_data.get('label', 'Unnamed Lane'),
                'allowed_types': lane_data.get('allowed_types', []),
                'allowed_labels': lane_data.get('allowed_labels', ['all'])
            })
        
        # Load stopline
        STOP_LINE = config['stopline']
        
        # Load traffic lights
        TL_ROIS.clear()
        TL_ROIS.extend(config['traffic_lights'])
        
        # ⚠️ CRITICAL: Enable TL color tracking if TL ROIs exist
        if TL_ROIS:
            self.tl_tracking_active = True
            print(f"🚦 HSV color tracking enabled for {len(TL_ROIS)} traffic lights")
        
        # Load direction zones
        DIRECTION_ROIS.clear()
        DIRECTION_ROIS.extend(config['direction_zones'])
        
        # ⚠️ CRITICAL: Pass direction ROIs to video thread
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.load_direction_rois(DIRECTION_ROIS)
            print(f"✅ Passed {len(DIRECTION_ROIS)} direction ROIs to VideoThread")
        
        # Load reference vector
        if config['reference_vector']:
            self.ref_vector_p1 = list(config['reference_vector'][0])
            self.ref_vector_p2 = list(config['reference_vector'][1])
            import math
            dx = self.ref_vector_p2[0] - self.ref_vector_p1[0]
            dy = self.ref_vector_p2[1] - self.ref_vector_p1[1]
            angle = math.degrees(math.atan2(dy, dx))
            self.ref_vector_label.setText(f"✅ Ref Vector: {angle:.1f}° ({dx:.0f}, {dy:.0f})")
            self.ref_vector_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            print(f"✅ Reference Vector loaded: {angle:.1f}° from {self.ref_vector_p1} to {self.ref_vector_p2}")
            
            # ⚠️ CRITICAL: Apply reference vector to TrajectoryAnalyzer
            if hasattr(self, 'thread') and self.thread is not None:
                self.thread.set_reference_vector_from_points(
                    tuple(self.ref_vector_p1), 
                    tuple(self.ref_vector_p2)
                )
                # Also set to old VehicleTracker for backward compatibility
                self.thread.set_reference_angle(angle)
                print(f"🎯 Applied reference vector to TrajectoryAnalyzer and VehicleTracker from config")
        else:
            self.ref_vector_p1 = None
            self.ref_vector_p2 = None
            self.ref_vector_label.setText("⚠️ Ref Vector: Not set - Set it for better accuracy!")
            self.ref_vector_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            if DIRECTION_ROIS:  # Warn if direction ROIs exist but no ref vector
                print("⚠️ WARNING: Direction ROIs loaded but Reference Vector NOT SET!")
                print("   → This may affect turn detection accuracy")
                print("   → Recommend: Set Reference Vector before starting detection")
        
        print(f"✅ Configuration applied to UI and global variables")
    
    # ========================================================================
    # View Toggle Methods
    # ========================================================================
    
    def toggle_lanes(self):
        """Toggle showing lanes"""
        self.show_lanes_flag = self.action_toggle_lanes.isChecked()
        self.show_lanes = self.show_lanes_flag
        print(f"{'👁️' if self.show_lanes_flag else '🙈'} Lanes: {'ON' if self.show_lanes_flag else 'OFF'}")
    
    def toggle_stopline(self):
        """Toggle showing stopline"""
        self.show_stopline_flag = self.action_toggle_stopline.isChecked()
        print(f"{'👁️' if self.show_stopline_flag else '🙈'} Stopline: {'ON' if self.show_stopline_flag else 'OFF'}")
    
    def toggle_traffic_lights(self):
        """Toggle showing traffic lights"""
        self.show_traffic_lights_flag = self.action_toggle_traffic_lights.isChecked()
        print(f"{'👁️' if self.show_traffic_lights_flag else '🙈'} Traffic Lights: {'ON' if self.show_traffic_lights_flag else 'OFF'}")
    
    def toggle_ref_vector(self):
        """Toggle showing reference vector"""
        self.show_ref_vector_flag = self.action_toggle_ref_vector.isChecked()
        print(f"{'👁️' if self.show_ref_vector_flag else '🙈'} Reference Vector: {'ON' if self.show_ref_vector_flag else 'OFF'}")
    
    # ========================================================================
    # Edit Lane Method
    # ========================================================================
    
    def start_edit_lane(self):
        """Start interactive lane editing - drag/add/delete keypoints, then configure settings"""
        global LANE_CONFIGS
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
        
        # Check if lanes exist
        if not LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes configured yet. Please add lanes first.")
            return
        
        # Always show selection dialog
        selection_dialog = QDialog(self)
        selection_dialog.setWindowTitle("Select Lane to Edit")
        selection_dialog.setMinimumSize(400, 300)
        sel_layout = QVBoxLayout(selection_dialog)
        
        sel_layout.addWidget(QLabel("<b>Select a lane to edit:</b>"))
        sel_lane_list = QListWidget()
        for idx, lane in enumerate(LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            points = lane.get('poly', [])
            sel_lane_list.addItem(f"Lane {idx}: {len(points)} points - Allowed: {', '.join(allowed)}")
        sel_layout.addWidget(sel_lane_list)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Edit")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        sel_layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(selection_dialog.reject)
        
        def on_ok():
            sel_idx = sel_lane_list.currentRow()
            if sel_idx >= 0:
                selection_dialog.selected_idx = sel_idx
                selection_dialog.accept()
            else:
                QMessageBox.warning(selection_dialog, "No Selection", "Please select a lane!")
        
        btn_ok.clicked.connect(on_ok)
        
        if selection_dialog.exec_() == QDialog.Rejected:
            return
        
        selected = getattr(selection_dialog, 'selected_idx', -1)
        if selected < 0:
            return
        
        # Enter interactive editing mode (like ROI editor)
        self.editing_lane_idx = selected
        self.dragging_lane_point_idx = None
        
        lane = LANE_CONFIGS[selected]
        
        # Update UI buttons
        self.btn_finish_edit_lane = QPushButton("Finish Lane Edit (Enter)")
        self.btn_finish_edit_lane.clicked.connect(self.finish_edit_lane)
        
        # Add finish button to control panel if not already there
        if hasattr(self, 'control_layout'):
            self.control_layout.addWidget(self.btn_finish_edit_lane)
        
        # Update status
        self.status_label.setText(
            f"Status: Editing Lane {selected+1} - {len(lane['poly'])} points | "
            f"Left-click+drag=move | Double-click=add | Delete key=remove selected | Press 'Finish' or Enter when done"
        )
        
        print(f"✏️ Editing Lane {selected+1}: ({len(lane['poly'])} points)")
        print(f"   Left-click and drag to move points")
        print(f"   Double-click near edge to add new point")
        print(f"   Click a point then press Delete key to remove")
        print(f"   Press 'Finish Lane Edit' button or Enter when done")
    
    def finish_edit_lane(self):
        """Finish lane editing and show vehicle type selection dialog"""
        if self.editing_lane_idx is None:
            return
        
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout
        
        selected = self.editing_lane_idx
        lane = LANE_CONFIGS[selected]
        
        # Remove finish button from control panel
        if hasattr(self, 'btn_finish_edit_lane'):
            self.btn_finish_edit_lane.deleteLater()
            del self.btn_finish_edit_lane
        
        # Stop editing mode
        self.editing_lane_idx = None
        self.dragging_lane_point_idx = None
        
        # Show vehicle type selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Configure Lane {selected + 1}")
        dialog.setMinimumSize(350, 250)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("<b>Select Allowed Vehicle Types:</b>"))
        
        allowed = lane.get('allowed_labels', ['all'])
        
        check_all = QCheckBox("All vehicles")
        check_all.setChecked('all' in allowed)
        layout.addWidget(check_all)
        
        check_xe_may = QCheckBox("Xe máy")
        check_xe_may.setChecked('xe may' in allowed)
        layout.addWidget(check_xe_may)
        
        check_o_to = QCheckBox("Ô tô")
        check_o_to.setChecked('o to' in allowed)
        layout.addWidget(check_o_to)
        
        check_xe_bus = QCheckBox("Xe bus")
        check_xe_bus.setChecked('xe bus' in allowed)
        layout.addWidget(check_xe_bus)
        
        check_xe_tai = QCheckBox("Xe tải")
        check_xe_tai.setChecked('xe tai' in allowed)
        layout.addWidget(check_xe_tai)
        
        # Save/Cancel buttons
        button_box = QHBoxLayout()
        btn_save = QPushButton("Save Changes")
        btn_cancel = QPushButton("Cancel")
        button_box.addWidget(btn_save)
        button_box.addWidget(btn_cancel)
        layout.addLayout(button_box)
        
        def save_changes():
            new_allowed = []
            if check_all.isChecked():
                new_allowed = ['all']
            else:
                if check_xe_may.isChecked():
                    new_allowed.append('xe may')
                if check_o_to.isChecked():
                    new_allowed.append('o to')
                if check_xe_bus.isChecked():
                    new_allowed.append('xe bus')
                if check_xe_tai.isChecked():
                    new_allowed.append('xe tai')
            
            if not new_allowed:
                QMessageBox.warning(dialog, "No Selection", "Please select at least one vehicle type or 'All'")
                return
            
            lane['allowed_labels'] = new_allowed
            self.update_lists()
            print(f"✅ Lane {selected + 1} configured: Allowed vehicles = {new_allowed}")
            dialog.accept()
        
        def cancel_changes():
            dialog.reject()
        
        btn_save.clicked.connect(save_changes)
        btn_cancel.clicked.connect(cancel_changes)
        
        # Update status
        self.status_label.setText("Status: Ready")
        
        dialog.exec_()
    
    def show_error(self, error_msg):
        self.status_label.setText(f"Status: Error - {error_msg}")
        print(f"❌ Error: {error_msg}")
    

    
    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

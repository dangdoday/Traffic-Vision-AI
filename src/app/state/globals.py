"""
Global State Variables
Quản lý tất cả biến global của ứng dụng
"""

# ============================================================
# TRAFFIC LIGHT ROIs
# ============================================================
# List of traffic light ROIs with type and current color
# Format: (x1, y1, x2, y2, tl_type, current_color)
# tl_type: 'đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải'
TL_ROIS = []

# ============================================================
# DIRECTION DETECTION ROIs  
# ============================================================
# Format: {'name': 'roi_1', 'points': [[x,y], ...], 
#          'allowed_directions': ['left', 'straight'], 
#          'primary_direction': 'straight'}
DIRECTION_ROIS = []

# Temporary variables for drawing direction ROIs
_tmp_direction_roi_pts = []
_selected_direction = 'straight'
_selected_directions_multi = ['straight']

# ============================================================
# ROI EDITING STATE
# ============================================================
_editing_roi_index = None  # Index of ROI being edited (None = not editing)
_editing_roi_type = None   # 'lane', 'direction', or 'tl'
_dragging_point_index = None  # Index of point being dragged
_hover_point_index = None     # Index of point being hovered
_hover_edge_indices = None    # (point1_idx, point2_idx) for edge insertion

# ============================================================
# LANE & STOPLINE
# ============================================================
LANE_CONFIGS = []
STOP_LINE = None  # Single stopline: ((x1,y1), (x2,y2))

# Temporary drawing variables
_tmp_lane_pts = []
_tmp_stop_point = None
_tmp_tl_point = None  # For manual TL ROI selection

# ============================================================
# DRAWING & DETECTION MODE
# ============================================================
# Drawing modes: 'lane', 'stopline', 'tl_manual', 'direction_roi', 'ref_vector', None
_drawing_mode = None
_detection_running = False
_show_all_boxes = True  # True = show all vehicles, False = show only violators

# ============================================================
# VEHICLE TRACKING & DIRECTION
# ============================================================
# Vehicle position history for direction calculation
VEHICLE_POSITIONS = {}  # {track_id: [(x, y, timestamp), ...]}
VEHICLE_DIRECTIONS = {}  # {track_id: 'straight' | 'left' | 'right' | 'unknown'}

# ============================================================
# VIOLATION TRACKING
# ============================================================
VIOLATOR_TRACK_IDS = set()
RED_LIGHT_VIOLATORS = set()
LANE_VIOLATORS = set()
PASSED_VEHICLES = set()  # Track vehicles that passed stop line

# ============================================================
# VEHICLE COUNTING
# ============================================================
MOTORBIKE_COUNT = set()  # Track motorbikes (xe máy)
CAR_COUNT = set()        # Track cars/trucks/buses (ô tô, xe tải, xe bus)

# ============================================================
# VEHICLE CLASSES
# ============================================================
VEHICLE_CLASSES = {
    0: "o to",
    1: "xe bus", 
    2: "xe dap",
    3: "xe may",
    4: "xe tai"
}
ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]


# ============================================================
# REFERENCE VECTOR (for direction calculation)
# ============================================================
REFERENCE_VECTOR = None  # ((x1, y1), (x2, y2)) - defines "straight" direction
REFERENCE_ANGLE = None   # Angle in degrees
_tmp_ref_vector_pt1 = None


def reset_all_state():
    """Reset tất cả state về giá trị ban đầu"""
    global TL_ROIS, DIRECTION_ROIS, LANE_CONFIGS, STOP_LINE
    global VEHICLE_POSITIONS, VEHICLE_DIRECTIONS
    global VIOLATOR_TRACK_IDS, RED_LIGHT_VIOLATORS, LANE_VIOLATORS
    global PASSED_VEHICLES, MOTORBIKE_COUNT, CAR_COUNT
    global _tmp_lane_pts, _tmp_stop_point, _tmp_tl_point
    global _tmp_direction_roi_pts, _drawing_mode, _detection_running
    global REFERENCE_VECTOR, REFERENCE_ANGLE, _tmp_ref_vector_pt1
    
    TL_ROIS.clear()
    DIRECTION_ROIS.clear()
    LANE_CONFIGS.clear()
    STOP_LINE = None
    
    VEHICLE_POSITIONS.clear()
    VEHICLE_DIRECTIONS.clear()
    
    VIOLATOR_TRACK_IDS.clear()
    RED_LIGHT_VIOLATORS.clear()
    LANE_VIOLATORS.clear()
    PASSED_VEHICLES.clear()
    MOTORBIKE_COUNT.clear()
    CAR_COUNT.clear()
    
    _tmp_lane_pts.clear()
    _tmp_stop_point = None
    _tmp_tl_point = None
    _tmp_direction_roi_pts.clear()
    
    _drawing_mode = None
    _detection_running = False
    
    REFERENCE_VECTOR = None
    REFERENCE_ANGLE = None
    _tmp_ref_vector_pt1 = None


def reset_detection_state():
    """Reset chỉ detection state, giữ nguyên ROIs"""
    global VEHICLE_POSITIONS, VEHICLE_DIRECTIONS
    global VIOLATOR_TRACK_IDS, RED_LIGHT_VIOLATORS, LANE_VIOLATORS
    global PASSED_VEHICLES, MOTORBIKE_COUNT, CAR_COUNT
    
    VEHICLE_POSITIONS.clear()
    VEHICLE_DIRECTIONS.clear()
    
    VIOLATOR_TRACK_IDS.clear()
    RED_LIGHT_VIOLATORS.clear()
    LANE_VIOLATORS.clear()
    PASSED_VEHICLES.clear()
    MOTORBIKE_COUNT.clear()
    CAR_COUNT.clear()

"""
Global state management for the application
Replaces scattered global variables
"""

# Traffic light ROIs
TL_ROIS = []  # List of (x1, y1, x2, y2, tl_type, current_color)

# Direction Detection ROIs
DIRECTION_ROIS = []
_tmp_direction_roi_pts = []
_selected_direction = 'straight'
_selected_directions_multi = ['straight']

# ROI Editing state
_editing_roi_index = None
_editing_roi_type = None
_dragging_point_index = None
_hover_point_index = None
_hover_edge_indices = None

# Vehicle tracking
VEHICLE_POSITIONS = {}
VEHICLE_DIRECTIONS = {}

# Lane configs
LANE_CONFIGS = []
STOP_LINE = None
_tmp_lane_pts = []
_tmp_stop_point = None
_tmp_tl_point = None

# Drawing mode
_drawing_mode = None

# Detection state
_detection_running = False
_show_all_boxes = True

# Detection tracking sets
VIOLATOR_TRACK_IDS = set()
RED_LIGHT_VIOLATORS = set()
LANE_VIOLATORS = set()
PASSED_VEHICLES = set()
MOTORBIKE_COUNT = set()
CAR_COUNT = set()

# Vehicle classes
VEHICLE_CLASSES = {0: "o to", 1: "xe bus", 2: "xe dap", 3: "xe may", 4: "xe tai"}
ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]

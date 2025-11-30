"""
Global State Management Module
Centralized storage for all detection and UI state variables
"""


class AppState:
    """Singleton class to manage all global application state"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Traffic light ROIs
        # Format: [(x1, y1, x2, y2, tl_type, current_color), ...]
        # tl_type: 'đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải'
        self.TL_ROIS = []
        
        # Direction Detection ROIs
        # Format: [{'name': 'roi_1', 'points': [[x,y], ...], 'allowed_directions': [...], 'primary_direction': 'straight'}, ...]
        self.DIRECTION_ROIS = []
        self._tmp_direction_roi_pts = []
        self._selected_direction = 'straight'
        self._selected_directions_multi = ['straight']
        
        # ROI Editing state
        self._editing_roi_index = None
        self._editing_roi_type = None  # 'lane', 'direction', or 'tl'
        self._dragging_point_index = None
        self._hover_point_index = None
        self._hover_edge_indices = None
        
        # Vehicle tracking
        self.VEHICLE_POSITIONS = {}  # {track_id: [(x, y, timestamp), ...]}
        self.VEHICLE_DIRECTIONS = {}  # {track_id: 'straight', 'left', 'right', 'unknown'}
        
        # Lane configurations
        self.LANE_CONFIGS = []
        self.STOP_LINE = None  # (p1, p2)
        self._tmp_lane_pts = []
        self._tmp_stop_point = None
        self._tmp_tl_point = None
        
        # Drawing mode
        self._drawing_mode = None  # 'lane', 'stopline', 'tl_manual', 'direction_roi', 'ref_vector', or None
        
        # Detection state
        self._detection_running = False
        self._show_all_boxes = True
        
        # Violation tracking
        self.VIOLATOR_TRACK_IDS = set()
        self.RED_LIGHT_VIOLATORS = set()
        self.LANE_VIOLATORS = set()
        self.PASSED_VEHICLES = set()
        self.MOTORBIKE_COUNT = set()
        self.CAR_COUNT = set()
        
        # Vehicle classes
        self.VEHICLE_CLASSES = {
            0: "o to",
            1: "xe bus",
            2: "xe dap",
            3: "xe may",
            4: "xe tai"
        }
        self.ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]
        
        self._initialized = True
    
    def reset_all_state(self):
        """Reset all state variables to initial values"""
        self.TL_ROIS.clear()
        self.DIRECTION_ROIS.clear()
        self._tmp_direction_roi_pts.clear()
        self._selected_direction = 'straight'
        self._selected_directions_multi = ['straight']
        
        self._editing_roi_index = None
        self._editing_roi_type = None
        self._dragging_point_index = None
        self._hover_point_index = None
        self._hover_edge_indices = None
        
        self.VEHICLE_POSITIONS.clear()
        self.VEHICLE_DIRECTIONS.clear()
        
        self.LANE_CONFIGS.clear()
        self.STOP_LINE = None
        self._tmp_lane_pts.clear()
        self._tmp_stop_point = None
        self._tmp_tl_point = None
        
        self._drawing_mode = None
        self._detection_running = False
        self._show_all_boxes = True
        
        self.reset_detection_state()
    
    def reset_detection_state(self):
        """Reset only detection-related counters"""
        self.VIOLATOR_TRACK_IDS.clear()
        self.RED_LIGHT_VIOLATORS.clear()
        self.LANE_VIOLATORS.clear()
        self.PASSED_VEHICLES.clear()
        self.MOTORBIKE_COUNT.clear()
        self.CAR_COUNT.clear()
        self.VEHICLE_POSITIONS.clear()
        self.VEHICLE_DIRECTIONS.clear()


# Create global instance
app_state = AppState()


# Convenience accessors for backward compatibility
def get_state():
    """Get the global app state instance"""
    return app_state


def reset_all_state():
    """Reset all state"""
    app_state.reset_all_state()


def reset_detection_state():
    """Reset detection counters"""
    app_state.reset_detection_state()

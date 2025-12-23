"""
Application State Management
Centralized global state for the traffic violation detector
"""


class AppState:
    """Central state management for the application"""
    
    def __init__(self):
        # Traffic Light ROIs
        # Format: [(x1, y1, x2, y2, tl_type, current_color), ...]
        # tl_type: 'đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải'
        self.TL_ROIS = []
        
        # Direction Detection ROIs
        # Format: [{'name': 'roi_1', 'points': [[x,y], ...], 
        #           'primary_direction': 'straight', 'secondary_directions': [], ...}, ...]
        self.DIRECTION_ROIS = []
        
        # Lane Configurations
        # Format: [{'poly': [...], 'points': [...], 'label': '...', 'allowed_types': [...]}, ...]
        self.LANE_CONFIGS = []
        
        # Stop Line
        # Format: ((x1, y1), (x2, y2)) or None
        self.STOP_LINE = None
        
        # Vehicle tracking for direction detection
        self.VEHICLE_POSITIONS = {}  # {track_id: [(x, y, timestamp), ...]}
        self.VEHICLE_DIRECTIONS = {}  # {track_id: 'straight', 'left', 'right', 'unknown'}
        
        # Detection variables
        self.VIOLATOR_TRACK_IDS = set()
        self.RED_LIGHT_VIOLATORS = set()
        self.LANE_VIOLATORS = set()
        self.PASSED_VEHICLES = set()
        self.MOTORBIKE_COUNT = set()  # Track motorbikes (xe máy)
        self.CAR_COUNT = set()  # Track cars/trucks/buses (ô tô, xe tải, xe bus)
        
        # Vehicle classes mapping
        self.VEHICLE_CLASSES = {
            0: "o to",
            1: "xe bus",
            2: "xe dap",
            3: "xe may",
            4: "xe tai"
        }
        self.ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]
        
        # Drawing/UI state
        self._tmp_lane_pts = []
        self._tmp_stop_point = None
        self._tmp_tl_point = None
        self._tmp_direction_roi_pts = []
        self._selected_direction = 'straight'
        self._selected_directions_multi = ['straight']
        self._drawing_mode = None  # 'lane', 'stopline', 'tl_manual', 'direction_roi', 'ref_vector', or None
        self._detection_running = False
        self._show_all_boxes = True  # True = show all vehicles, False = show only violators
        
        # ROI Editing variables
        self._editing_roi_index = None
        self._editing_roi_type = None  # 'lane', 'direction', or 'tl'
        self._dragging_point_index = None
        self._hover_point_index = None
        self._hover_edge_indices = None  # (point1_idx, point2_idx)
    
    def reset_detection_state(self):
        """Reset detection-related state (violations, counts, etc.)"""
        self.VIOLATOR_TRACK_IDS.clear()
        self.RED_LIGHT_VIOLATORS.clear()
        self.LANE_VIOLATORS.clear()
        self.PASSED_VEHICLES.clear()
        self.MOTORBIKE_COUNT.clear()
        self.CAR_COUNT.clear()
        self.VEHICLE_POSITIONS.clear()
        self.VEHICLE_DIRECTIONS.clear()
    
    def reset_all(self):
        """Reset all state"""
        self.TL_ROIS.clear()
        self.DIRECTION_ROIS.clear()
        self.LANE_CONFIGS.clear()
        self.STOP_LINE = None
        self.reset_detection_state()
        self._tmp_lane_pts.clear()
        self._tmp_stop_point = None
        self._tmp_tl_point = None
        self._tmp_direction_roi_pts.clear()
        self._selected_direction = 'straight'
        self._selected_directions_multi = ['straight']
        self._drawing_mode = None
        self._detection_running = False
        self._editing_roi_index = None
        self._editing_roi_type = None
        self._dragging_point_index = None
        self._hover_point_index = None
        self._hover_edge_indices = None


# Global singleton instance
_app_state = None


def get_app_state():
    """Get the global AppState singleton instance"""
    global _app_state
    if _app_state is None:
        _app_state = AppState()
    return _app_state

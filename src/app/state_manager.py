"""
Global State Manager
Centralized state management for the application
"""


class GlobalState:
    """Centralized application state"""
    
    def __init__(self):
        """Initialize global state"""
        # Traffic light ROIs
        # Format: List of (x1, y1, x2, y2, tl_type, current_color)
        self.tl_rois = []
        
        # Direction ROIs
        # Format: {'name': 'roi_1', 'points': [[x,y], ...], 
        #          'allowed_directions': ['left', 'straight'], 
        #          'primary_direction': 'straight'}
        self.direction_rois = []
        
        # Lane configurations
        self.lane_configs = []
        
        # Stopline
        self.stop_line = None  # (p1, p2) tuple
        
        # Temporary drawing variables
        self.tmp_lane_pts = []
        self.tmp_stop_point = None
        self.tmp_tl_point = None
        self.tmp_direction_roi_pts = []
        
        # Drawing mode
        self.drawing_mode = None  # 'lane', 'stopline', 'tl_manual', 'direction_roi', 'ref_vector'
        
        # Selected direction for drawing
        self.selected_direction = 'straight'
        
        # Detection state
        self.detection_running = False
        self.show_all_boxes = True  # True = all vehicles, False = only violators
        
        # Violation tracking
        self.violator_track_ids = set()
        self.red_light_violators = set()
        self.lane_violators = set()
        self.passed_vehicles = set()
        
        # Vehicle counting
        self.motorbike_count = set()
        self.car_count = set()
        
        # Vehicle tracking for direction
        self.vehicle_positions = {}  # {track_id: [(x, y), ...]}
        self.vehicle_directions = {}  # {track_id: 'left'/'straight'/'right'}
        
        # Reference vector (for tilted camera)
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        
        # ROI editing state
        self.editing_roi_index = None
        self.editing_roi_type = None
        self.show_direction_rois = True
        
        # Vehicle classes
        self.vehicle_classes = {
            0: "o to", 
            1: "xe bus", 
            2: "xe dap", 
            3: "xe may", 
            4: "xe tai"
        }
        self.allowed_vehicle_ids = [0, 1, 2, 3, 4]
    
    def reset_detection_state(self):
        """Reset detection-related state"""
        self.detection_running = False
        self.violator_track_ids.clear()
        self.red_light_violators.clear()
        self.lane_violators.clear()
        self.passed_vehicles.clear()
        self.motorbike_count.clear()
        self.car_count.clear()
        self.vehicle_positions.clear()
        self.vehicle_directions.clear()
        print("♻️ Detection state reset")
    
    def reset_all_rois(self):
        """Reset all ROIs and configurations"""
        self.tl_rois.clear()
        self.direction_rois.clear()
        self.lane_configs.clear()
        self.stop_line = None
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        print("♻️ All ROIs reset")
    
    def clear_temporary_drawing(self):
        """Clear temporary drawing data"""
        self.tmp_lane_pts.clear()
        self.tmp_stop_point = None
        self.tmp_tl_point = None
        self.tmp_direction_roi_pts.clear()
        self.drawing_mode = None
    
    def get_tl_roi_count(self):
        """Get number of traffic light ROIs"""
        return len(self.tl_rois)
    
    def get_direction_roi_count(self):
        """Get number of direction ROIs"""
        return len(self.direction_rois)
    
    def get_lane_count(self):
        """Get number of lanes"""
        return len(self.lane_configs)
    
    def has_stopline(self):
        """Check if stopline is configured"""
        return self.stop_line is not None
    
    def has_reference_vector(self):
        """Check if reference vector is set"""
        return self.ref_vector_p1 is not None and self.ref_vector_p2 is not None


# Global singleton instance
_state = GlobalState()


def get_global_state():
    """
    Get global state instance.
    
    Returns:
        GlobalState: Global state singleton
    """
    return _state


# Backward compatibility functions
def get_tl_rois():
    """Get traffic light ROIs"""
    return _state.tl_rois


def get_direction_rois():
    """Get direction ROIs"""
    return _state.direction_rois


def get_lane_configs():
    """Get lane configurations"""
    return _state.lane_configs


def get_stop_line():
    """Get stopline"""
    return _state.stop_line


def set_stop_line(stopline):
    """Set stopline"""
    _state.stop_line = stopline


def is_detection_running():
    """Check if detection is running"""
    return _state.detection_running


def set_detection_running(running):
    """Set detection running state"""
    _state.detection_running = running


def get_show_all_boxes():
    """Get show all boxes state"""
    return _state.show_all_boxes


def set_show_all_boxes(show_all):
    """Set show all boxes state"""
    _state.show_all_boxes = show_all

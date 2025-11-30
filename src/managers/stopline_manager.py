"""
Stopline Manager
Manages stopline detection and checking if vehicles cross it
"""
from utils.geometry import point_to_segment_distance


class StoplineManager:
    """Manages stopline and checks vehicle positions"""
    
    def __init__(self):
        """Initialize stopline manager"""
        self.stopline = None  # (p1, p2) where p1, p2 are (x, y) tuples
        self.passed_vehicles = set()  # Track IDs that crossed
    
    def set_stopline(self, p1, p2):
        """
        Set the stopline coordinates.
        
        Args:
            p1: (x, y) first point
            p2: (x, y) second point
        """
        self.stopline = (p1, p2)
        print(f"🚦 Stopline set: {p1} -> {p2}")
    
    def clear_stopline(self):
        """Remove the stopline"""
        self.stopline = None
        self.passed_vehicles.clear()
        print("🗑️ Stopline cleared")
    
    def has_stopline(self):
        """
        Check if stopline is configured.
        
        Returns:
            bool: True if stopline exists
        """
        return self.stopline is not None
    
    def is_on_stopline(self, cx, cy, threshold=15):
        """
        Check if a point is on the stopline.
        
        Args:
            cx, cy: Point coordinates
            threshold: Distance threshold (pixels)
            
        Returns:
            bool: True if point is within threshold distance of stopline
        """
        if not self.has_stopline():
            return False
        
        p1, p2 = self.stopline
        dist = point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
        
        return dist < threshold
    
    def check_vehicle_crossed(self, track_id, cx, cy, threshold=15):
        """
        Check if vehicle has crossed the stopline.
        
        Args:
            track_id: Vehicle tracking ID
            cx, cy: Vehicle center position
            threshold: Distance threshold
            
        Returns:
            bool: True if vehicle just crossed (not seen before)
        """
        if not self.has_stopline():
            return False
        
        # Check if on stopline
        if self.is_on_stopline(cx, cy, threshold):
            # Check if first time crossing
            if track_id not in self.passed_vehicles:
                self.passed_vehicles.add(track_id)
                return True
        
        return False
    
    def reset_passed_vehicles(self):
        """Clear the list of vehicles that passed the stopline"""
        self.passed_vehicles.clear()
    
    def get_stopline(self):
        """
        Get current stopline coordinates.
        
        Returns:
            tuple or None: ((x1, y1), (x2, y2)) or None
        """
        return self.stopline
    
    def draw_stopline(self, frame):
        """
        Draw stopline on frame.
        
        Args:
            frame: OpenCV image (modified in place)
            
        Returns:
            frame: Modified frame
        """
        import cv2
        
        if not self.has_stopline():
            return frame
        
        p1, p2 = self.stopline
        cv2.line(frame, p1, p2, (0, 0, 255), 4)
        cv2.putText(
            frame, "STOP LINE", 
            (p1[0], p1[1] - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, (0, 0, 255), 2
        )
        
        return frame


# Global instance for backward compatibility
_manager = StoplineManager()


def is_on_stop_line(cx, cy, threshold=15):
    """
    Legacy function for backward compatibility.
    
    Args:
        cx, cy: Point coordinates
        threshold: Distance threshold
        
    Returns:
        bool: True if on stopline
    """
    return _manager.is_on_stopline(cx, cy, threshold)


def set_global_stopline(p1, p2):
    """
    Set global stopline.
    
    Args:
        p1: (x, y) first point
        p2: (x, y) second point
    """
    _manager.set_stopline(p1, p2)


def clear_global_stopline():
    """Clear global stopline"""
    _manager.clear_stopline()


def get_global_stopline():
    """
    Get global stopline.
    
    Returns:
        tuple or None: ((x1, y1), (x2, y2)) or None
    """
    return _manager.get_stopline()

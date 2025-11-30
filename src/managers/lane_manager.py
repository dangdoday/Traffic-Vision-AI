"""
Lane Manager
Manages lane configurations and vehicle type checking
"""
from utils.geometry import point_in_polygon, calculate_polygon_center
import cv2
import numpy as np


class LaneManager:
    """Manages lanes and vehicle permissions"""
    
    def __init__(self):
        """Initialize lane manager"""
        self.lanes = []  # List of lane configs
    
    def add_lane(self, polygon, allowed_types=None):
        """
        Add a new lane.
        
        Args:
            polygon: List of (x, y) points
            allowed_types: List of allowed vehicle type names (or None for all)
            
        Returns:
            int: Lane index
        """
        lane = {
            'poly': polygon,
            'points': polygon,  # Backward compat
            'allowed_labels': allowed_types or ['all'],
            'allowed_types': allowed_types or []
        }
        
        self.lanes.append(lane)
        print(f"✅ Added lane {len(self.lanes)}: {len(polygon)} points, types: {allowed_types}")
        
        return len(self.lanes) - 1
    
    def remove_lane(self, index):
        """
        Remove a lane by index.
        
        Args:
            index: Lane index
            
        Returns:
            bool: True if removed successfully
        """
        if 0 <= index < len(self.lanes):
            del self.lanes[index]
            print(f"🗑️ Removed lane {index}")
            return True
        return False
    
    def clear_all_lanes(self):
        """Remove all lanes"""
        self.lanes.clear()
        print("🗑️ All lanes cleared")
    
    def get_lane(self, index):
        """
        Get lane configuration.
        
        Args:
            index: Lane index
            
        Returns:
            dict or None: Lane config
        """
        if 0 <= index < len(self.lanes):
            return self.lanes[index]
        return None
    
    def is_point_in_any_lane(self, point):
        """
        Check if point is in any lane.
        
        Args:
            point: (x, y) coordinates
            
        Returns:
            int or None: Lane index if found, None otherwise
        """
        for idx, lane in enumerate(self.lanes):
            if point_in_polygon(point, lane['poly']):
                return idx
        return None
    
    def is_vehicle_allowed_in_lane(self, lane_idx, vehicle_type):
        """
        Check if vehicle type is allowed in lane.
        
        Args:
            lane_idx: Lane index
            vehicle_type: Vehicle type name
            
        Returns:
            bool: True if allowed
        """
        if lane_idx is None or lane_idx >= len(self.lanes):
            return True  # No lane restriction
        
        lane = self.lanes[lane_idx]
        allowed = lane.get('allowed_labels', ['all'])
        
        # 'all' means any vehicle allowed
        if 'all' in allowed:
            return True
        
        return vehicle_type in allowed
    
    def draw_lanes(self, frame, alpha=0.3):
        """
        Draw all lanes on frame.
        
        Args:
            frame: OpenCV image
            alpha: Overlay transparency (0-1)
            
        Returns:
            frame: Frame with lanes drawn
        """
        if not self.lanes:
            return frame
        
        overlay = frame.copy()
        
        for idx, lane in enumerate(self.lanes, start=1):
            poly = lane['poly']
            pts = np.array(poly, dtype=np.int32)
            
            # Fill polygon
            cv2.fillPoly(overlay, [pts], (0, 255, 255))
            
            # Draw border
            cv2.polylines(overlay, [pts], isClosed=True, 
                         color=(0, 200, 200), thickness=2)
            
            # Draw label
            center = calculate_polygon_center(poly)
            cv2.putText(
                overlay, f"L{idx}", 
                (center[0] - 15, center[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2
            )
        
        # Blend with original frame
        out = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        return out
    
    def get_lane_count(self):
        """
        Get number of configured lanes.
        
        Returns:
            int: Number of lanes
        """
        return len(self.lanes)
    
    def get_all_lanes(self):
        """
        Get all lane configurations.
        
        Returns:
            list: List of lane dicts
        """
        return self.lanes
    
    def set_lanes(self, lanes):
        """
        Set lanes from configuration.
        
        Args:
            lanes: List of lane dicts
        """
        self.lanes = lanes
        print(f"📂 Loaded {len(lanes)} lanes from configuration")


# Global instance for backward compatibility
_manager = LaneManager()


def add_global_lane(polygon, allowed_types=None):
    """
    Add lane to global manager.
    
    Args:
        polygon: List of (x, y) points
        allowed_types: List of allowed vehicle types
        
    Returns:
        int: Lane index
    """
    return _manager.add_lane(polygon, allowed_types)


def get_global_lane_configs():
    """
    Get global lane configurations.
    
    Returns:
        list: List of lane dicts
    """
    return _manager.get_all_lanes()


def clear_global_lanes():
    """Clear all global lanes"""
    _manager.clear_all_lanes()

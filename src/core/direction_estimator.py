"""
Direction Estimator
Calculates vehicle movement direction based on position history
"""
import math
from collections import defaultdict


class DirectionEstimator:
    """Estimates vehicle direction from trajectory"""
    
    def __init__(self, max_history=10, min_positions=5):
        """
        Initialize direction estimator.
        
        Args:
            max_history: Maximum number of positions to keep
            min_positions: Minimum positions required for direction calculation
        """
        self.max_history = max_history
        self.min_positions = min_positions
        self.vehicle_positions = defaultdict(list)
        self.vehicle_directions = {}
    
    def update_position(self, track_id, position):
        """
        Add new position for vehicle.
        
        Args:
            track_id: Vehicle tracking ID
            position: (x, y) position tuple
        """
        self.vehicle_positions[track_id].append(position)
        
        # Keep only last N positions
        if len(self.vehicle_positions[track_id]) > self.max_history:
            self.vehicle_positions[track_id] = self.vehicle_positions[track_id][-self.max_history:]
    
    def calculate_direction(self, track_id):
        """
        Calculate vehicle direction based on position history.
        
        Args:
            track_id: Vehicle tracking ID
            
        Returns:
            str: 'left', 'straight', 'right', or 'unknown'
        """
        if track_id not in self.vehicle_positions:
            return 'unknown'
        
        positions = self.vehicle_positions[track_id]
        
        # Need minimum positions
        if len(positions) < self.min_positions:
            return 'unknown'
        
        # Calculate direction vector from first to last position
        start_x, start_y = positions[0][0], positions[0][1]
        end_x, end_y = positions[-1][0], positions[-1][1]
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        # Calculate angle in degrees (-180 to 180)
        angle = math.degrees(math.atan2(dy, dx))
        
        # Check if enough movement
        if abs(dx) < 20 and abs(dy) < 20:
            return 'unknown'  # Not enough movement
        
        # Determine direction based on angle
        # Assuming camera view: forward = down (positive y), right = positive x
        direction = self._angle_to_direction(angle, dx, dy)
        
        # Store calculated direction
        self.vehicle_directions[track_id] = direction
        
        return direction
    
    def _angle_to_direction(self, angle, dx, dy):
        """
        Convert angle and displacement to direction.
        
        Args:
            angle: Angle in degrees
            dx: X displacement
            dy: Y displacement
            
        Returns:
            str: 'left', 'straight', 'right', or 'unknown'
        """
        # Moving right (positive x, small angle)
        if abs(angle) < 30:
            if dy > 0:  # Also moving down (forward)
                return 'right'
            return 'unknown'
        
        # Moving left (negative x, large angle)
        elif abs(angle) > 150:
            if dy > 0:
                return 'left'
            return 'unknown'
        
        # Moving down-left to down
        elif 30 <= angle <= 150:
            if -45 <= angle <= 45:
                return 'straight'
            elif angle > 45:
                return 'left'
            else:
                return 'straight'
        
        # Other directions - check primary movement
        else:
            if dy > 50:  # Primarily moving forward
                if abs(dx) < 30:
                    return 'straight'
                elif dx > 0:
                    return 'right'
                else:
                    return 'left'
            return 'unknown'
    
    def get_direction(self, track_id):
        """
        Get stored direction for vehicle.
        
        Args:
            track_id: Vehicle tracking ID
            
        Returns:
            str: Last calculated direction or 'unknown'
        """
        return self.vehicle_directions.get(track_id, 'unknown')
    
    def clear_vehicle(self, track_id):
        """
        Clear tracking data for vehicle.
        
        Args:
            track_id: Vehicle tracking ID
        """
        if track_id in self.vehicle_positions:
            del self.vehicle_positions[track_id]
        if track_id in self.vehicle_directions:
            del self.vehicle_directions[track_id]
    
    def clear_all(self):
        """Clear all tracking data"""
        self.vehicle_positions.clear()
        self.vehicle_directions.clear()


# Global singleton for backward compatibility
_estimator = DirectionEstimator()


def calculate_vehicle_direction(track_id, current_pos):
    """
    Legacy function for backward compatibility.
    
    Args:
        track_id: Vehicle tracking ID
        current_pos: (x, y) position
        
    Returns:
        str: 'left', 'straight', 'right', or 'unknown'
    """
    _estimator.update_position(track_id, current_pos)
    return _estimator.calculate_direction(track_id)

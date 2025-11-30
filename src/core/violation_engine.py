"""
Violation Engine
Logic for detecting traffic light violations based on direction and light state
"""


class ViolationChecker:
    """Check if vehicle violates traffic light rules"""
    
    def __init__(self, tl_rois, vehicle_directions):
        """
        Initialize violation checker.
        
        Args:
            tl_rois: List of traffic light ROIs
            vehicle_directions: Dict of vehicle directions by track_id
        """
        self.tl_rois = tl_rois
        self.vehicle_directions = vehicle_directions
    
    def check_violation(self, track_id, vehicle_direction):
        """
        Check if vehicle crossing stopline violates traffic rules.
        
        Args:
            track_id: Vehicle tracking ID
            vehicle_direction: Direction ('left', 'straight', 'right', 'unknown')
            
        Returns:
            tuple: (is_violation: bool, reason: str)
        """
        if len(self.tl_rois) == 0:
            return (False, "No traffic lights configured")
        
        # Store direction for this vehicle
        self.vehicle_directions[track_id] = vehicle_direction
        
        # Collect traffic light states
        has_any_green = False
        has_any_red = False
        has_matching_green_arrow = False
        has_matching_red_arrow = False
        
        # Check if there are dedicated turn lights
        has_left_turn_light = any(
            tl_type == 'rẽ trái' 
            for _, _, _, _, tl_type, _ in self.tl_rois
        )
        has_right_turn_light = any(
            tl_type == 'rẽ phải' 
            for _, _, _, _, tl_type, _ in self.tl_rois
        )
        
        red_lights = []
        green_lights = []
        
        # Check each traffic light
        for tl_idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(self.tl_rois):
            if current_color == 'xanh':  # GREEN
                has_any_green = True
                green_lights.append(f"{tl_type}")
                
                if self._is_green_allowed(
                    tl_type, vehicle_direction, 
                    has_left_turn_light, has_right_turn_light
                ):
                    has_matching_green_arrow = True
            
            elif current_color == 'đỏ':  # RED
                has_any_red = True
                red_lights.append(f"{tl_type}")
                
                if self._is_red_forbidden(
                    tl_type, vehicle_direction,
                    has_left_turn_light, has_right_turn_light
                ):
                    has_matching_red_arrow = True
        
        # Decision logic
        if has_matching_green_arrow:
            return (False, f"✅ GREEN light for direction - ALLOWED ({', '.join(green_lights)})")
        
        if has_matching_red_arrow:
            if vehicle_direction == 'unknown':
                return (True, f"🚨 RED LIGHT VIOLATION - direction unknown ({', '.join(red_lights)})")
            else:
                return (True, f"🚨 RED LIGHT VIOLATION - {vehicle_direction} ({', '.join(red_lights)})")
        
        if has_any_red:
            return (True, f"🚨 RED LIGHT VIOLATION - no matching green ({', '.join(red_lights)})")
        
        if has_any_green:
            return (False, f"✅ GREEN lights - ALLOWED ({', '.join(green_lights)})")
        
        return (False, f"⚠️ No clear violation - dir={vehicle_direction}")
    
    def _is_green_allowed(self, tl_type, vehicle_direction, 
                         has_left_turn_light, has_right_turn_light):
        """
        Check if green light allows vehicle direction.
        
        Args:
            tl_type: Traffic light type
            vehicle_direction: Vehicle direction
            has_left_turn_light: Whether left turn light exists
            has_right_turn_light: Whether right turn light exists
            
        Returns:
            bool: True if green light allows this direction
        """
        # Circular green = all directions allowed
        if tl_type == 'tròn':
            # Exception: If dedicated turn light exists, must use that
            if vehicle_direction == 'left' and has_left_turn_light:
                return False
            if vehicle_direction == 'right' and has_right_turn_light:
                return False
            return True
        
        # Straight light
        if tl_type == 'đi thẳng':
            if vehicle_direction == 'straight':
                return True
            # Can turn left/right on straight green if no dedicated turn light
            if vehicle_direction == 'left' and not has_left_turn_light:
                return True
            if vehicle_direction == 'right' and not has_right_turn_light:
                return True
            return False
        
        # Turn lights
        if tl_type == 'rẽ trái' and vehicle_direction == 'left':
            return True
        if tl_type == 'rẽ phải' and vehicle_direction == 'right':
            return True
        
        return False
    
    def _is_red_forbidden(self, tl_type, vehicle_direction,
                         has_left_turn_light, has_right_turn_light):
        """
        Check if red light forbids vehicle direction.
        
        Args:
            tl_type: Traffic light type
            vehicle_direction: Vehicle direction
            has_left_turn_light: Whether left turn light exists
            has_right_turn_light: Whether right turn light exists
            
        Returns:
            bool: True if red light forbids this direction
        """
        # Circular red = all directions forbidden
        if tl_type == 'tròn':
            return True
        
        # Straight red light
        if tl_type == 'đi thẳng':
            if vehicle_direction == 'straight':
                return True
            # Turn on straight red forbidden if no dedicated turn light
            if vehicle_direction == 'left' and not has_left_turn_light:
                return True
            return False
        
        # Turn lights
        if tl_type == 'rẽ trái' and vehicle_direction == 'left':
            return True
        if tl_type == 'rẽ phải' and vehicle_direction == 'right':
            return True
        
        return False


def check_tl_violation(track_id, vehicle_direction, tl_rois, vehicle_directions):
    """
    Legacy function for backward compatibility.
    
    Args:
        track_id: Vehicle tracking ID
        vehicle_direction: Direction string
        tl_rois: List of traffic light ROIs
        vehicle_directions: Dict of vehicle directions
        
    Returns:
        tuple: (is_violation: bool, reason: str)
    """
    checker = ViolationChecker(tl_rois, vehicle_directions)
    return checker.check_violation(track_id, vehicle_direction)

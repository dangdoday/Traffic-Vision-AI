"""
Traffic Light State Detector
Detects traffic light colors using HSV color space analysis
"""
import cv2
import numpy as np


class TrafficLightDetector:
    """Detects traffic light color from ROI image"""
    
    # HSV ranges for traffic light colors
    RED_LOWER_1 = np.array([0, 100, 80])
    RED_UPPER_1 = np.array([10, 255, 255])
    RED_LOWER_2 = np.array([160, 100, 80])
    RED_UPPER_2 = np.array([180, 255, 255])
    
    YELLOW_LOWER = np.array([15, 100, 80])
    YELLOW_UPPER = np.array([35, 255, 255])
    
    GREEN_LOWER = np.array([40, 100, 80])
    GREEN_UPPER = np.array([90, 255, 255])
    
    def __init__(self, min_confidence=0.02):
        """
        Initialize traffic light detector.
        
        Args:
            min_confidence: Minimum pixel ratio to detect a color (default: 0.02 = 2%)
        """
        self.min_confidence = min_confidence
    
    def detect_color(self, roi):
        """
        Detect traffic light color from ROI image.
        
        Args:
            roi: BGR image ROI of traffic light
            
        Returns:
            str: 'đỏ', 'vàng', 'xanh', or 'unknown'
        """
        if roi is None or roi.size == 0:
            return 'unknown'
        
        try:
            # Resize to standard size for consistent detection
            roi_resized = cv2.resize(roi, (20, 60))
            hsv = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2HSV)
            
            # Create masks for each color
            mask_red = cv2.bitwise_or(
                cv2.inRange(hsv, self.RED_LOWER_1, self.RED_UPPER_1),
                cv2.inRange(hsv, self.RED_LOWER_2, self.RED_UPPER_2)
            )
            mask_yellow = cv2.inRange(hsv, self.YELLOW_LOWER, self.YELLOW_UPPER)
            mask_green = cv2.inRange(hsv, self.GREEN_LOWER, self.GREEN_UPPER)
            
            # Calculate ratios
            red_ratio = mask_red.mean() / 255.0
            yellow_ratio = mask_yellow.mean() / 255.0
            green_ratio = mask_green.mean() / 255.0
            
            # Check if any color is detected with sufficient confidence
            max_ratio = max(red_ratio, yellow_ratio, green_ratio)
            if max_ratio < self.min_confidence:
                return 'unknown'
            
            # Return dominant color
            if red_ratio == max_ratio:
                return 'đỏ'
            elif yellow_ratio == max_ratio:
                return 'vàng'
            else:
                return 'xanh'
                
        except Exception as e:
            print(f"⚠️ Error detecting traffic light color: {e}")
            return 'unknown'
    
    def detect_pixel_state(self, roi):
        """
        Alternative detection method with simpler logic.
        
        Args:
            roi: BGR image ROI
            
        Returns:
            str: 'den_do', 'den_vang', 'den_xanh', or 'unknown'
        """
        if roi is None or roi.size == 0:
            return 'unknown'
        
        try:
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
            
            if r == m:
                return 'den_do'
            elif y == m:
                return 'den_vang'
            else:
                return 'den_xanh'
                
        except Exception:
            return 'unknown'


# Singleton instance
_detector = TrafficLightDetector()


def detect_traffic_light_color(roi):
    """
    Convenience function to detect traffic light color.
    
    Args:
        roi: BGR image ROI of traffic light
        
    Returns:
        str: 'đỏ', 'vàng', 'xanh', or 'unknown'
    """
    return _detector.detect_color(roi)


def classify_tl_color(roi):
    """
    Legacy function for backward compatibility.
    
    Args:
        roi: BGR image ROI
        
    Returns:
        str: 'red', 'yellow', 'green', or 'unknown'
    """
    color = _detector.detect_color(roi)
    
    # Convert to English
    color_map = {
        'đỏ': 'red',
        'vàng': 'yellow',
        'xanh': 'green',
        'unknown': 'unknown'
    }
    
    return color_map.get(color, 'unknown')


def tl_pixel_state(roi):
    """
    Legacy function for backward compatibility.
    
    Args:
        roi: BGR image ROI
        
    Returns:
        str: 'den_do', 'den_vang', 'den_xanh', or 'unknown'
    """
    return _detector.detect_pixel_state(roi)

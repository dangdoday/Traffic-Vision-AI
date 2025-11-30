"""
Traffic Light Color Classification Module
Handles traffic light color detection and state management
"""

import cv2
import numpy as np


def tl_pixel_state(roi):
    """Legacy traffic light state detection (simple version)
    
    Args:
        roi: Image region containing traffic light
        
    Returns:
        'den_do', 'den_vang', 'den_xanh', or 'unknown'
    """
    if roi is None or roi.size == 0:
        return 'unknown'
    
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
    
    return 'den_do' if r == m else ('den_vang' if y == m else 'den_xanh')


def classify_tl_color(roi):
    """Improved traffic light color classification
    
    Args:
        roi: Image region containing traffic light
        
    Returns:
        'đỏ' (red), 'vàng' (yellow), 'xanh' (green), or 'unknown'
    """
    if roi is None or roi.size == 0:
        return "unknown"

    roi = cv2.resize(roi, (20, 60))
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Define color ranges
    lower_red1 = np.array([0, 100, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 80])
    upper_red2 = np.array([180, 255, 255])

    lower_yellow = np.array([15, 100, 80])
    upper_yellow = np.array([35, 255, 255])

    lower_green = np.array([40, 100, 80])
    upper_green = np.array([90, 255, 255])

    # Create masks
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | \
               cv2.inRange(hsv, lower_red2, upper_red2)
    mask_yel = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_grn = cv2.inRange(hsv, lower_green, upper_green)

    # Calculate ratios
    red_ratio = mask_red.mean() / 255.0
    yellow_ratio = mask_yel.mean() / 255.0
    green_ratio = mask_grn.mean() / 255.0

    if max(red_ratio, yellow_ratio, green_ratio) < 0.02:
        return "unknown"

    if red_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "đỏ"
    elif yellow_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "vàng"
    else:
        return "xanh"


def map_color_to_vietnamese(color):
    """Map English color names to Vietnamese
    
    Args:
        color: 'red', 'yellow', 'green', or 'unknown'
        
    Returns:
        'đỏ', 'vàng', 'xanh', or 'unknown'
    """
    mapping = {
        'red': 'đỏ',
        'yellow': 'vàng',
        'green': 'xanh',
        'unknown': 'unknown'
    }
    return mapping.get(color, color)

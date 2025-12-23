"""
Utility functions for geometry and detection
"""

import cv2
import numpy as np
import math


def point_in_polygon(point, poly):
    """Check if point is inside polygon"""
    x, y = point
    pts = np.array(poly, dtype=np.int32)
    return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Calculate distance from point to line segment"""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return np.sqrt((px - x1)**2 + (py - y1)**2)
    t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return np.sqrt((px - nx)**2 + (py - ny)**2)


def is_on_stop_line(cx, cy, stop_line, threshold=15):
    """Check if point is on stop line"""
    if stop_line is None:
        return False
    p1, p2 = stop_line
    dist = point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
    return dist < threshold


def tl_pixel_state(roi):
    """Detect traffic light color using HSV"""
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
    """Classify traffic light color"""
    if roi is None or roi.size == 0:
        return "unknown"
    
    roi = cv2.resize(roi, (20, 60))
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    mask_red = cv2.inRange(hsv, np.array([0, 100, 80]), np.array([10, 255, 255])) | \
               cv2.inRange(hsv, np.array([160, 100, 80]), np.array([180, 255, 255]))
    mask_yel = cv2.inRange(hsv, np.array([15, 100, 80]), np.array([35, 255, 255]))
    mask_grn = cv2.inRange(hsv, np.array([40, 100, 80]), np.array([90, 255, 255]))
    
    red_ratio = mask_red.mean() / 255.0
    yellow_ratio = mask_yel.mean() / 255.0
    green_ratio = mask_grn.mean() / 255.0
    
    if max(red_ratio, yellow_ratio, green_ratio) < 0.02:
        return "unknown"
    
    if red_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "red"
    elif yellow_ratio == max(red_ratio, yellow_ratio, green_ratio):
        return "yellow"
    else:
        return "green"

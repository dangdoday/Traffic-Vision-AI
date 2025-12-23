"""
Geometry utility functions for traffic violation detection
"""
import numpy as np
import cv2


def point_in_polygon(point, poly):
    """Check if a point is inside a polygon
    
    Args:
        point: (x, y) tuple
        poly: List of points [[x1, y1], [x2, y2], ...]
    
    Returns:
        bool: True if point is inside polygon
    """
    x, y = point
    pts = np.array(poly, dtype=np.int32)
    return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Calculate distance from a point to a line segment
    
    Args:
        px, py: Point coordinates
        x1, y1, x2, y2: Line segment endpoints
    
    Returns:
        float: Distance from point to segment
    """
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return np.sqrt((px - x1)**2 + (py - y1)**2)
    t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return np.sqrt((px - nx)**2 + (py - ny)**2)


def is_on_stop_line(cx, cy, stop_line, threshold=15):
    """Check if point is on the stopline
    
    Args:
        cx, cy: Point coordinates
        stop_line: ((x1, y1), (x2, y2)) tuple or None
        threshold: Distance threshold in pixels
    
    Returns:
        bool: True if point is within threshold distance of stopline
    """
    if stop_line is None:
        return False
    p1, p2 = stop_line
    dist = point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
    return dist < threshold

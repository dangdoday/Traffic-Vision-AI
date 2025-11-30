# src/app/geometry.py
"""
Geometry helper functions

Tách các hàm hình học ra khỏi MainWindow:
- point_in_polygon
- point_to_segment_distance
- is_on_stop_line
"""

import cv2
import numpy as np


def point_in_polygon(point, polygon):
    """
    Check if a point is inside a polygon using cv2.pointPolygonTest

    Args:
        point: (x, y)
        polygon: list[(x, y), ...]

    Returns:
        bool
    """
    if not polygon or len(polygon) < 3:
        return False

    x, y = point
    pts = np.array(polygon, dtype=np.int32)
    res = cv2.pointPolygonTest(pts, (float(x), float(y)), False)
    return res >= 0


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """
    Distance from point (px, py) to line segment (x1,y1)-(x2,y2)
    """
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return np.hypot(px - x1, py - y1)

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return np.hypot(px - nx, py - ny)


def is_on_stop_line(cx, cy, stop_line, threshold=15):
    """
    Check if point (cx, cy) nằm gần vạch dừng (stop_line)
    stop_line: ((x1,y1), (x2,y2)) hoặc None
    """
    if stop_line is None:
        return False
    (x1, y1), (x2, y2) = stop_line
    dist = point_to_segment_distance(cx, cy, x1, y1, x2, y2)
    return dist < threshold

"""
Geometry Utilities
Helper functions for geometric calculations
"""

import cv2
import numpy as np
from typing import List, Tuple


def point_in_polygon(point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
    """
    Check if a point is inside a polygon using cv2
    
    Args:
        point: (x, y) coordinate
        polygon: List of (x, y) vertices
        
    Returns:
        True if point is inside polygon
    """
    if not polygon or len(polygon) < 3:
        return False
    
    poly_array = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(poly_array, point, False)
    return result >= 0


def calculate_polygon_center(polygon: List[Tuple[int, int]]) -> Tuple[int, int]:
    """
    Calculate the center point of a polygon
    
    Args:
        polygon: List of (x, y) vertices
        
    Returns:
        (center_x, center_y)
    """
    if not polygon:
        return (0, 0)
    
    x_coords = [p[0] for p in polygon]
    y_coords = [p[1] for p in polygon]
    
    center_x = int(np.mean(x_coords))
    center_y = int(np.mean(y_coords))
    
    return (center_x, center_y)


def simplify_polygon(polygon: List[Tuple[int, int]], 
                     epsilon_factor: float = 0.01) -> List[Tuple[int, int]]:
    """
    Simplify polygon using Douglas-Peucker algorithm
    
    Args:
        polygon: List of (x, y) vertices
        epsilon_factor: Approximation accuracy (as fraction of perimeter)
        
    Returns:
        Simplified polygon
    """
    if len(polygon) < 3:
        return polygon
    
    poly_array = np.array(polygon, dtype=np.float32)
    
    # Calculate epsilon based on perimeter
    perimeter = cv2.arcLength(poly_array, True)
    epsilon = epsilon_factor * perimeter
    
    # Apply approximation
    approx = cv2.approxPolyDP(poly_array, epsilon, True)
    
    # Convert back to list of tuples
    simplified = [(int(p[0][0]), int(p[0][1])) for p in approx]
    
    return simplified if len(simplified) >= 3 else polygon


def calculate_line_intersection(line1: Tuple[Tuple[int, int], Tuple[int, int]],
                                line2: Tuple[Tuple[int, int], Tuple[int, int]]) -> Tuple[int, int]:
    """
    Calculate intersection point of two lines
    
    Args:
        line1: ((x1, y1), (x2, y2))
        line2: ((x3, y3), (x4, y4))
        
    Returns:
        (x, y) intersection point or None if parallel
    """
    (x1, y1), (x2, y2) = line1
    (x3, y3), (x4, y4) = line2
    
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    if abs(denom) < 1e-6:  # Parallel lines
        return None
    
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    
    x = x1 + t * (x2 - x1)
    y = y1 + t * (y2 - y1)
    
    return (int(x), int(y))


def distance_point_to_line(point: Tuple[int, int],
                           line_start: Tuple[int, int],
                           line_end: Tuple[int, int]) -> float:
    """
    Calculate perpendicular distance from point to line
    
    Args:
        point: (x, y)
        line_start: (x1, y1)
        line_end: (x2, y2)
        
    Returns:
        Distance in pixels
    """
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Line length
    line_len = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    if line_len < 1e-6:
        return np.sqrt((x - x1)**2 + (y - y1)**2)
    
    # Distance using cross product
    dist = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / line_len
    
    return dist

def point_in_polygon(point, polygon):
    """Check if a point is inside a polygon using the ray-casting algorithm."""
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def distance_point_to_segment(px, py, x1, y1, x2, y2):
    """Calculate the distance from a point to a line segment."""
    import numpy as np
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1

    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return np.hypot(px - x1, py - y1)

    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return np.hypot(px - x2, py - y2)

    b = c1 / c2
    bx = x1 + b * vx
    by = y1 + b * vy
    return np.hypot(px - bx, py - by)


# Alias for compatibility
point_to_segment_distance = distance_point_to_segment


def calculate_polygon_center(polygon):
    """
    Calculate the center point of a polygon
    
    Args:
        polygon: List of (x, y) vertices
        
    Returns:
        (center_x, center_y)
    """
    import numpy as np
    if not polygon:
        return (0, 0)
    
    x_coords = [p[0] for p in polygon]
    y_coords = [p[1] for p in polygon]
    
    center_x = int(np.mean(x_coords))
    center_y = int(np.mean(y_coords))
    
    return (center_x, center_y)

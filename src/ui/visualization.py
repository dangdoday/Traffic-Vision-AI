"""
Visualization Utilities
Functions for drawing overlays on video frames
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional
from constants.app_constants import DIRECTION_COLORS, DIRECTION_LABELS


def draw_polygon_overlay(frame: np.ndarray,
                        polygon: List[Tuple[int, int]],
                        color: Tuple[int, int, int],
                        alpha: float = 0.25,
                        border_thickness: int = 2) -> np.ndarray:
    """
    Draw a semi-transparent filled polygon with border
    
    Args:
        frame: Input image
        polygon: List of (x, y) vertices
        color: BGR color tuple
        alpha: Transparency (0=transparent, 1=opaque)
        border_thickness: Border line thickness
        
    Returns:
        Frame with polygon overlay
    """
    if len(polygon) < 3:
        return frame
    
    overlay = frame.copy()
    pts = np.array(polygon, dtype=np.int32)
    
    # Fill polygon
    cv2.fillPoly(overlay, [pts], color)
    
    # Draw border on original frame
    cv2.polylines(frame, [pts], True, color, border_thickness)
    
    # Blend overlay
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    
    return frame


def draw_text_with_background(frame: np.ndarray,
                              text: str,
                              position: Tuple[int, int],
                              font_scale: float = 0.8,
                              color: Tuple[int, int, int] = (255, 255, 255),
                              bg_color: Tuple[int, int, int] = (0, 0, 0),
                              thickness: int = 2,
                              padding: int = 5) -> np.ndarray:
    """
    Draw text with background rectangle
    
    Args:
        frame: Input image
        text: Text to draw
        position: (x, y) top-left position
        font_scale: Font size scale
        color: Text color (BGR)
        bg_color: Background color (BGR)
        thickness: Text thickness
        padding: Padding around text
        
    Returns:
        Frame with text
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )
    
    x, y = position
    
    # Draw background rectangle
    cv2.rectangle(
        frame,
        (x - padding, y - text_height - padding),
        (x + text_width + padding, y + baseline + padding),
        bg_color,
        -1
    )
    
    # Draw text
    cv2.putText(
        frame, text, (x, y),
        font, font_scale, color, thickness, cv2.LINE_AA
    )
    
    return frame


def draw_direction_rois(frame: np.ndarray,
                       direction_rois: List[Dict],
                       show_labels: bool = True,
                       alpha: float = 0.25) -> np.ndarray:
    """
    Draw all direction ROIs with labels
    
    Args:
        frame: Input image
        direction_rois: List of ROI dictionaries
        show_labels: Whether to show direction labels
        alpha: Transparency for filled regions
        
    Returns:
        Frame with ROIs drawn
    """
    for roi in direction_rois:
        points = roi.get('points', [])
        direction = roi.get('direction', 'unknown')
        
        if len(points) < 3:
            continue
        
        # Get color for this direction
        color = DIRECTION_COLORS.get(direction, DIRECTION_COLORS['unknown'])
        
        # Draw polygon
        frame = draw_polygon_overlay(frame, points, color, alpha)
        
        # Draw label if enabled
        if show_labels:
            # Calculate center
            center_x = int(np.mean([p[0] for p in points]))
            center_y = int(np.mean([p[1] for p in points]))
            
            # Get label text
            label = DIRECTION_LABELS.get(direction, direction.upper())
            
            # Draw label
            cv2.putText(
                frame, label, (center_x - 50, center_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA
            )
    
    return frame


def draw_lanes(frame: np.ndarray,
              lane_configs: List[Dict],
              alpha: float = 0.3) -> np.ndarray:
    """
    Draw lane polygons
    
    Args:
        frame: Input image
        lane_configs: List of lane configuration dictionaries
        alpha: Transparency
        
    Returns:
        Frame with lanes drawn
    """
    overlay = frame.copy()
    
    for idx, lane in enumerate(lane_configs, start=1):
        poly = lane.get('poly', [])
        if len(poly) < 3:
            continue
        
        pts = np.array(poly, dtype=np.int32)
        color = (255, 0, 0)  # Blue for lanes
        
        # Fill polygon
        cv2.fillPoly(overlay, [pts], color)
        
        # Draw border
        cv2.polylines(frame, [pts], True, color, 2)
        
        # Draw label
        center_x = int(np.mean([p[0] for p in poly]))
        center_y = int(np.mean([p[1] for p in poly]))
        cv2.putText(
            frame, f"L{idx}", (center_x - 15, center_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
        )
    
    # Blend
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    
    return frame


def draw_stop_line(frame: np.ndarray,
                  stop_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]],
                  color: Tuple[int, int, int] = (0, 0, 255),
                  thickness: int = 3) -> np.ndarray:
    """
    Draw stop line
    
    Args:
        frame: Input image
        stop_line: ((x1, y1), (x2, y2)) or None
        color: Line color (BGR)
        thickness: Line thickness
        
    Returns:
        Frame with stop line drawn
    """
    if stop_line is None:
        return frame
    
    p1, p2 = stop_line
    cv2.line(frame, p1, p2, color, thickness)
    cv2.putText(
        frame, "STOP LINE", (p1[0], p1[1] - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
    )
    
    return frame


def draw_reference_vector(frame: np.ndarray,
                         ref_p1: Optional[Tuple[int, int]],
                         ref_p2: Optional[Tuple[int, int]],
                         color: Tuple[int, int, int] = (255, 0, 255),
                         thickness: int = 3) -> np.ndarray:
    """
    Draw reference vector for direction detection
    
    Args:
        frame: Input image
        ref_p1: Start point (x, y)
        ref_p2: End point (x, y)
        color: Line color (BGR)
        thickness: Line thickness
        
    Returns:
        Frame with reference vector drawn
    """
    if ref_p1 is None or ref_p2 is None:
        return frame
    
    # Draw line
    cv2.line(frame, ref_p1, ref_p2, color, thickness)
    
    # Draw arrow head
    cv2.arrowedLine(frame, ref_p1, ref_p2, color, thickness, tipLength=0.1)
    
    # Draw angle text
    import math
    dx = ref_p2[0] - ref_p1[0]
    dy = ref_p2[1] - ref_p1[1]
    angle = math.degrees(math.atan2(dy, dx))
    
    mid_x = (ref_p1[0] + ref_p2[0]) // 2
    mid_y = (ref_p1[1] + ref_p2[1]) // 2
    
    cv2.putText(
        frame, f"REF: {angle:.1f} deg", (mid_x + 10, mid_y - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
    )
    
    return frame

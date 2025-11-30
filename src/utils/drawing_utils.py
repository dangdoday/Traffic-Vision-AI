"""
Drawing Utilities Module
Functions for drawing lanes, ROIs, traffic lights, and other visual elements
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional


# Color constants
DIRECTION_COLORS = {
    'left': (0, 0, 255),      # Red
    'right': (0, 165, 255),   # Orange
    'straight': (0, 255, 0),  # Green
    'unknown': (128, 128, 128)  # Gray
}

DIRECTION_LABELS = {
    'left': 'RE TRAI',
    'right': 'RE PHAI',
    'straight': 'DI THANG',
    'unknown': 'UNKNOWN'
}

TL_TYPE_COLORS = {
    'tròn': (255, 255, 0),      # Cyan - Circular light
    'đi thẳng': (0, 255, 0),    # Green - Straight arrow
    'rẽ trái': (0, 0, 255),     # Red - Left arrow
    'rẽ phải': (0, 165, 255)    # Orange - Right arrow
}


def draw_lanes(frame, lane_configs, alpha=0.3):
    """Draw lane polygons with transparency
    
    Args:
        frame: Image to draw on
        lane_configs: List of lane dictionaries with 'poly' key
        alpha: Transparency factor (0-1)
        
    Returns:
        Modified frame
    """
    if not lane_configs:
        return frame
    
    overlay = frame.copy()
    
    for idx, lane in enumerate(lane_configs, start=1):
        poly = lane["poly"]
        pts = np.array(poly, dtype=np.int32)
        
        # Fill polygon
        cv2.fillPoly(overlay, [pts], (0, 255, 255))
        
        # Draw border
        cv2.polylines(overlay, [pts], isClosed=True, color=(0, 200, 200), thickness=2)
        
        # Draw label at center
        cx = int(sum(p[0] for p in poly) / len(poly))
        cy = int(sum(p[1] for p in poly) / len(poly))
        cv2.putText(overlay, f"L{idx}", (cx-15, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    # Blend overlay with original frame
    out = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    return out


def draw_stop_line(frame, stop_line):
    """Draw stop line
    
    Args:
        frame: Image to draw on
        stop_line: Tuple of ((x1, y1), (x2, y2)) or None
        
    Returns:
        Modified frame
    """
    if stop_line is None:
        return frame
    
    p1, p2 = stop_line
    cv2.line(frame, p1, p2, (0, 0, 255), 4)
    cv2.putText(frame, "STOP LINE", (p1[0], p1[1]-10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    return frame


def draw_direction_rois(frame, direction_rois, roi_editor=None, alpha=0.25):
    """Draw direction ROIs with transparency and labels
    
    Args:
        frame: Image to draw on
        direction_rois: List of ROI dictionaries with 'points' and 'direction' keys
        roi_editor: Optional ROI editor for drawing editing overlay
        alpha: Transparency factor (0-1)
        
    Returns:
        Modified frame
    """
    if not direction_rois:
        return frame
    
    overlay = frame.copy()
    
    for i, roi in enumerate(direction_rois):
        pts = np.array(roi['points'], dtype=np.int32)
        direction = roi.get('direction', 'unknown')
        color = DIRECTION_COLORS.get(direction, DIRECTION_COLORS['unknown'])
        
        # Fill polygon
        cv2.fillPoly(overlay, [pts], color)
        
        # Draw border
        cv2.polylines(frame, [pts], True, color, 2)
        
        # Draw label at center
        center_x = int(np.mean([p[0] for p in roi['points']]))
        center_y = int(np.mean([p[1] for p in roi['points']]))
        
        direction_text = DIRECTION_LABELS.get(direction, direction.upper())
        cv2.putText(frame, direction_text, (center_x - 50, center_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # Blend overlay with frame
    frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
    
    # Draw editing overlay if in edit mode
    if roi_editor and roi_editor.is_editing():
        roi_idx = roi_editor.editing_roi_index
        if roi_idx < len(direction_rois):
            points = direction_rois[roi_idx]['points']
            roi_editor.draw_editing_overlay(frame, points)
    
    return frame


def draw_traffic_light_rois(frame, tl_rois):
    """Draw traffic light ROIs with current color state
    
    Args:
        frame: Image to draw on
        tl_rois: List of (x1, y1, x2, y2, tl_type, current_color) tuples
        
    Returns:
        Modified frame
    """
    if not tl_rois:
        return frame
    
    for idx, (x1, y1, x2, y2, tl_type, current_color) in enumerate(tl_rois):
        # Get color based on TL type
        box_color = TL_TYPE_COLORS.get(tl_type, (255, 255, 255))
        
        # Draw ROI box
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
        
        # Draw label with type and current color
        label = f"TL{idx+1} {tl_type}"
        cv2.putText(frame, label, (x1, y1-25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
        # Draw current color indicator
        color_text = current_color if current_color else "?"
        color_indicator_color = (0, 0, 255) if current_color == 'đỏ' else \
                                (0, 255, 255) if current_color == 'vàng' else \
                                (0, 255, 0) if current_color == 'xanh' else \
                                (128, 128, 128)
        
        cv2.putText(frame, color_text, (x1, y1-5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_indicator_color, 2)
    
    return frame


def draw_vehicle_boxes(frame, detections, show_all=True, violators=None, 
                       vehicle_directions=None, vehicle_classes=None):
    """Draw bounding boxes for detected vehicles
    
    Args:
        frame: Image to draw on
        detections: List of detection results with boxes, track_ids, classes
        show_all: If True, show all vehicles. If False, only violators
        violators: Set of track IDs that are violators
        vehicle_directions: Dict mapping track_id -> direction string
        vehicle_classes: Dict mapping class_id -> class name
        
    Returns:
        Modified frame
    """
    if violators is None:
        violators = set()
    if vehicle_directions is None:
        vehicle_directions = {}
    if vehicle_classes is None:
        vehicle_classes = {}
    
    for det in detections:
        track_id = det.get('track_id')
        x1, y1, x2, y2 = det.get('box', [0, 0, 0, 0])
        class_id = det.get('class_id', -1)
        conf = det.get('confidence', 0.0)
        
        is_violator = track_id in violators
        
        # Skip non-violators if show_all is False
        if not show_all and not is_violator:
            continue
        
        # Choose color based on violation status
        color = (0, 0, 255) if is_violator else (0, 255, 0)
        
        # Draw box
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        
        # Draw label
        class_name = vehicle_classes.get(class_id, f"class_{class_id}")
        direction = vehicle_directions.get(track_id, "unknown")
        label = f"ID{track_id} {class_name} {direction}"
        
        if is_violator:
            label += " [VI PHAM]"
        
        cv2.putText(frame, label, (int(x1), int(y1)-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    return frame


def draw_temporary_points(frame, temp_points, color=(0, 255, 255), closed=False):
    """Draw temporary points being drawn (e.g., for lane or ROI creation)
    
    Args:
        frame: Image to draw on
        temp_points: List of (x, y) points
        color: Color to draw with
        closed: If True, connect last point to first
        
    Returns:
        Modified frame
    """
    if not temp_points:
        return frame
    
    # Draw lines connecting points
    for i in range(len(temp_points) - 1):
        cv2.line(frame, temp_points[i], temp_points[i+1], color, 2)
    
    # Close the polygon if requested
    if closed and len(temp_points) >= 3:
        cv2.line(frame, temp_points[-1], temp_points[0], color, 2)
    
    # Draw points
    for pt in temp_points:
        cv2.circle(frame, pt, 5, color, -1)
    
    return frame


def draw_reference_vector(frame, ref_vector_p1, ref_vector_p2):
    """Draw reference vector for direction detection
    
    Args:
        frame: Image to draw on
        ref_vector_p1: Start point (x, y)
        ref_vector_p2: End point (x, y)
        
    Returns:
        Modified frame
    """
    if ref_vector_p1 is None or ref_vector_p2 is None:
        return frame
    
    # Draw line
    cv2.line(frame, ref_vector_p1, ref_vector_p2, (255, 0, 255), 3)
    
    # Draw arrow head
    cv2.arrowedLine(frame, ref_vector_p1, ref_vector_p2, (255, 0, 255), 3, 
                    tipLength=0.3)
    
    # Draw label
    cv2.putText(frame, "REF VECTOR", (ref_vector_p1[0], ref_vector_p1[1]-10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    
    return frame


def draw_statistics(frame, stats_dict, position=(10, 30)):
    """Draw statistics text on frame
    
    Args:
        frame: Image to draw on
        stats_dict: Dictionary of stat_name -> value
        position: Starting (x, y) position for text
        
    Returns:
        Modified frame
    """
    x, y = position
    line_height = 25
    
    for i, (key, value) in enumerate(stats_dict.items()):
        text = f"{key}: {value}"
        cv2.putText(frame, text, (x, y + i * line_height),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return frame

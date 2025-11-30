"""
Overlay Drawer
Draws various overlays on video frames (ROIs, lanes, stoplines, etc.)
"""
import cv2
import numpy as np
import math


class OverlayDrawer:
    """Draws overlays on video frames"""
    
    # Direction colors
    DIRECTION_COLORS = {
        'left': (0, 0, 255),      # Red
        'right': (0, 165, 255),   # Orange
        'straight': (0, 255, 0),  # Green
        'unknown': (128, 128, 128)  # Gray
    }
    
    # Direction labels (Vietnamese without accents)
    DIRECTION_LABELS = {
        'left': 'RE TRAI',
        'right': 'RE PHAI',
        'straight': 'DI THANG',
        'unknown': 'UNKNOWN'
    }
    
    def __init__(self, alpha=0.25):
        """
        Initialize overlay drawer.
        
        Args:
            alpha: Transparency for overlays (0-1)
        """
        self.alpha = alpha
    
    def draw_direction_rois(self, frame, direction_rois):
        """
        Draw direction ROIs on frame.
        
        Args:
            frame: OpenCV image
            direction_rois: List of direction ROI dicts
            
        Returns:
            frame: Frame with ROIs drawn
        """
        if not direction_rois:
            return frame
        
        overlay = frame.copy()
        
        for i, roi in enumerate(direction_rois):
            pts = np.array(roi['points'], dtype=np.int32)
            
            # Get primary direction for color
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown'))
            color = self.DIRECTION_COLORS.get(primary_dir, self.DIRECTION_COLORS['unknown'])
            
            # Fill polygon with transparency
            cv2.fillPoly(overlay, [pts], color)
            
            # Draw border
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Draw label at center
            center_x = int(np.mean([p[0] for p in roi['points']]))
            center_y = int(np.mean([p[1] for p in roi['points']]))
            
            direction_text = self.DIRECTION_LABELS.get(primary_dir, primary_dir.upper())
            cv2.putText(
                frame, direction_text,
                (center_x - 50, center_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
            )
        
        # Blend overlay with frame
        frame = cv2.addWeighted(overlay, self.alpha, frame, 1 - self.alpha, 0)
        
        return frame
    
    def draw_traffic_lights(self, frame, tl_rois):
        """
        Draw traffic light ROIs with current color.
        
        Args:
            frame: OpenCV image
            tl_rois: List of (x1, y1, x2, y2, tl_type, current_color)
            
        Returns:
            frame: Frame with TL ROIs drawn
        """
        for idx, tl_data in enumerate(tl_rois):
            x1, y1, x2, y2, tl_type, current_color = tl_data
            
            # Color code by current light color
            box_color = (128, 128, 128)  # Gray default
            if current_color == 'đỏ':
                box_color = (0, 0, 255)  # Red
            elif current_color == 'xanh':
                box_color = (0, 255, 0)  # Green
            elif current_color == 'vàng':
                box_color = (0, 255, 255)  # Yellow
            
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            
            # Draw label
            label_text = f"TL{idx+1}[{tl_type}]: {current_color}"
            cv2.putText(
                frame, label_text,
                (x1, max(0, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2, cv2.LINE_AA
            )
        
        return frame
    
    def draw_reference_vector(self, frame, p1, p2):
        """
        Draw reference vector for direction calibration.
        
        Args:
            frame: OpenCV image
            p1: (x, y) start point
            p2: (x, y) end point
            
        Returns:
            frame: Frame with vector drawn
        """
        if p1 is None or p2 is None:
            return frame
        
        # Draw arrow
        cv2.arrowedLine(frame, p1, p2, (255, 0, 255), 3, tipLength=0.05)
        
        # Draw start/end points
        cv2.circle(frame, p1, 6, (255, 0, 255), -1)
        cv2.circle(frame, p2, 6, (255, 0, 255), -1)
        
        # Calculate and draw angle
        mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle = math.degrees(math.atan2(dy, dx))
        
        cv2.putText(
            frame, f"REF: {angle:.1f} deg",
            (mid[0] + 10, mid[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA
        )
        
        return frame
    
    def draw_temporary_lane(self, frame, points):
        """
        Draw temporary lane being drawn.
        
        Args:
            frame: OpenCV image
            points: List of (x, y) points
            
        Returns:
            frame: Frame with temp lane drawn
        """
        if not points:
            return frame
        
        pts_tmp = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [pts_tmp], isClosed=False, color=(0, 255, 0), thickness=2)
        
        for p in points:
            cv2.circle(frame, p, 4, (0, 255, 0), -1)
        
        return frame
    
    def draw_temporary_stopline_point(self, frame, point):
        """
        Draw temporary stopline point.
        
        Args:
            frame: OpenCV image
            point: (x, y) point
            
        Returns:
            frame: Frame with point drawn
        """
        if point is None:
            return frame
        
        cv2.circle(frame, point, 5, (0, 0, 255), -1)
        
        return frame
    
    def draw_temporary_direction_roi(self, frame, points, direction='straight'):
        """
        Draw temporary direction ROI being drawn.
        
        Args:
            frame: OpenCV image
            points: List of [x, y] points
            direction: Direction string
            
        Returns:
            frame: Frame with temp ROI drawn
        """
        if not points:
            return frame
        
        color = self.DIRECTION_COLORS.get(direction, (128, 128, 128))
        pts_tmp = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [pts_tmp], isClosed=False, color=color, thickness=2)
        
        for p in points:
            cv2.circle(frame, tuple(p), 5, color, -1)
        
        return frame
    
    def draw_temporary_tl_point(self, frame, point):
        """
        Draw temporary traffic light point.
        
        Args:
            frame: OpenCV image
            point: (x, y) point
            
        Returns:
            frame: Frame with point drawn
        """
        if point is None:
            return frame
        
        cv2.circle(frame, point, 6, (0, 200, 255), -1)
        cv2.putText(
            frame, "P1",
            (point[0] + 8, point[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2
        )
        
        return frame
    
    def draw_text_with_background(self, frame, text, position, 
                                  font_scale=0.6, color=(255, 255, 255),
                                  bg_color=(0, 0, 0), thickness=2, padding=5):
        """
        Draw text with background rectangle.
        
        Args:
            frame: OpenCV image
            text: Text to draw
            position: (x, y) position
            font_scale: Font scale
            color: Text color (BGR)
            bg_color: Background color (BGR)
            thickness: Text thickness
            padding: Padding around text
            
        Returns:
            frame: Frame with text drawn
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        # Draw background rectangle
        x, y = position
        cv2.rectangle(
            frame,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            bg_color,
            -1
        )
        
        # Draw text
        cv2.putText(
            frame, text,
            (x, y),
            font, font_scale, color, thickness, cv2.LINE_AA
        )
        
        return frame

"""
ROI Editor Tool
Công cụ chỉnh sửa điểm và độ cong của ROI sau khi vẽ

Features:
- Di chuyển điểm: Click và kéo điểm
- Thêm điểm: Double-click trên cạnh ROI
- Xóa điểm: Right-click trên điểm
- Làm mượt: Giảm số điểm và tạo đường cong mượt hơn
"""

import numpy as np
import cv2


class ROIEditor:
    """Handle ROI editing operations"""
    
    def __init__(self):
        self.editing_roi_index = None  # Index of ROI being edited
        self.dragging_point_index = None  # Index of point being dragged
        self.hover_point_index = None  # Index of point being hovered
        self.hover_edge_indices = None  # (p1_idx, p2_idx) of edge being hovered
        self.point_radius = 8  # Click detection radius for points
        self.edge_threshold = 10  # Click detection threshold for edges
        
    def start_editing(self, roi_index):
        """Start editing a specific ROI"""
        self.editing_roi_index = roi_index
        self.dragging_point_index = None
        self.hover_point_index = None
        self.hover_edge_indices = None
        print(f"✏️ Started editing ROI {roi_index}")
        
    def finish_editing(self):
        """Finish editing current ROI"""
        if self.editing_roi_index is not None:
            print(f"✅ Finished editing ROI {self.editing_roi_index}")
        self.editing_roi_index = None
        self.dragging_point_index = None
        self.hover_point_index = None
        self.hover_edge_indices = None
        
    def is_editing(self):
        """Check if currently editing an ROI"""
        return self.editing_roi_index is not None
    
    def handle_mouse_press(self, x, y, button, points):
        """
        Handle mouse press event
        
        Args:
            x, y: Mouse position in frame coordinates
            button: 'left', 'right', or 'middle'
            points: List of ROI points [[x,y], ...]
            
        Returns:
            True if event was handled, False otherwise
        """
        if not self.is_editing():
            return False
        
        # Right click = delete point
        if button == 'right':
            return self._delete_point_at(x, y, points)
        
        # Left click = start dragging
        if button == 'left':
            return self._start_dragging_point(x, y, points)
        
        return False
    
    def handle_mouse_move(self, x, y, points):
        """
        Handle mouse move event
        
        Args:
            x, y: Mouse position in frame coordinates
            points: List of ROI points [[x,y], ...]
        """
        if not self.is_editing():
            return
        
        # Update dragging
        if self.dragging_point_index is not None:
            points[self.dragging_point_index] = [x, y]
            return
        
        # Update hover state
        self._update_hover_state(x, y, points)
    
    def handle_mouse_release(self):
        """Handle mouse release event"""
        if self.dragging_point_index is not None:
            print(f"✅ Finished dragging point {self.dragging_point_index}")
            self.dragging_point_index = None
    
    def handle_double_click(self, x, y, points):
        """
        Handle double-click to insert new point on edge
        
        Args:
            x, y: Mouse position in frame coordinates
            points: List of ROI points [[x,y], ...]
            
        Returns:
            True if point was inserted, False otherwise
        """
        if not self.is_editing():
            return False
        
        # Find closest edge
        min_dist = float('inf')
        insert_after_idx = None
        
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            dist = self._point_to_segment_dist(x, y, p1[0], p1[1], p2[0], p2[1])
            if dist < min_dist:
                min_dist = dist
                insert_after_idx = i
        
        # Insert if close enough to an edge
        if min_dist < 20:
            points.insert(insert_after_idx + 1, [x, y])
            print(f"➕ Inserted point at index {insert_after_idx + 1}, now {len(points)} points")
            return True
        
        return False
    
    def _delete_point_at(self, x, y, points):
        """Delete point at position (x, y)"""
        if len(points) <= 3:
            print("⚠️ Cannot delete - need at least 3 points")
            return False
        
        # Find closest point
        min_dist = float('inf')
        closest_idx = None
        for i, pt in enumerate(points):
            dist = np.sqrt((pt[0] - x)**2 + (pt[1] - y)**2)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        
        if min_dist < self.point_radius * 2:
            del points[closest_idx]
            print(f"🗑️ Deleted point {closest_idx}, now {len(points)} points")
            return True
        
        return False
    
    def _start_dragging_point(self, x, y, points):
        """Start dragging a point if clicked on one"""
        for i, pt in enumerate(points):
            dist = np.sqrt((pt[0] - x)**2 + (pt[1] - y)**2)
            if dist < self.point_radius * 2:
                self.dragging_point_index = i
                print(f"🖱️ Dragging point {i}")
                return True
        return False
    
    def _update_hover_state(self, x, y, points):
        """Update hover state for visual feedback"""
        # Check if hovering over a point
        self.hover_point_index = None
        self.hover_edge_indices = None
        
        min_dist = float('inf')
        for i, pt in enumerate(points):
            dist = np.sqrt((pt[0] - x)**2 + (pt[1] - y)**2)
            if dist < self.point_radius * 2 and dist < min_dist:
                min_dist = dist
                self.hover_point_index = i
        
        # If not hovering over point, check if hovering over edge
        if self.hover_point_index is None:
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                dist = self._point_to_segment_dist(x, y, p1[0], p1[1], p2[0], p2[1])
                if dist < self.edge_threshold:
                    self.hover_edge_indices = (i, (i + 1) % len(points))
                    break
    
    @staticmethod
    def _point_to_segment_dist(px, py, x1, y1, x2, y2):
        """Calculate distance from point to line segment"""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1)**2 + (py - y1)**2)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
        nx = x1 + t * dx
        ny = y1 + t * dy
        return np.sqrt((px - nx)**2 + (py - ny)**2)
    
    def draw_editing_overlay(self, frame, points):
        """
        Draw editing overlay on frame (points, hover effects, etc.)
        
        Args:
            frame: OpenCV image to draw on
            points: List of ROI points [[x,y], ...]
        """
        if not self.is_editing() or len(points) == 0:
            return
        
        # Draw ROI polygon with thicker line
        pts = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 255), 3)
        
        # Draw all points
        for i, pt in enumerate(points):
            x, y = int(pt[0]), int(pt[1])
            
            # Different colors for different states
            if i == self.dragging_point_index:
                color = (0, 0, 255)  # Red for dragging
                radius = 10
            elif i == self.hover_point_index:
                color = (0, 255, 0)  # Green for hover
                radius = 9
            else:
                color = (255, 255, 0)  # Cyan for normal
                radius = 7
            
            cv2.circle(frame, (x, y), radius, color, -1)
            cv2.circle(frame, (x, y), radius + 2, (255, 255, 255), 2)
            
            # Draw point index
            cv2.putText(frame, str(i), (x + 12, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Highlight hovered edge
        if self.hover_edge_indices is not None:
            i1, i2 = self.hover_edge_indices
            p1 = points[i1]
            p2 = points[i2]
            cv2.line(frame, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
                    (0, 255, 0), 4)
            
            # Draw insertion hint
            mid_x = (p1[0] + p2[0]) // 2
            mid_y = (p1[1] + p2[1]) // 2
            cv2.circle(frame, (int(mid_x), int(mid_y)), 5, (0, 255, 0), -1)
            cv2.putText(frame, "Double-click to insert", (int(mid_x) + 10, int(mid_y)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    @staticmethod
    def smooth_roi(points, epsilon_factor=0.01):
        """
        Smooth ROI by reducing number of points using Douglas-Peucker algorithm
        
        Args:
            points: List of ROI points [[x,y], ...]
            epsilon_factor: Approximation accuracy (0.01 = 1% of perimeter)
            
        Returns:
            Smoothed list of points
        """
        if len(points) < 4:
            return points
        
        pts = np.array(points, dtype=np.float32)
        
        # Calculate perimeter
        perimeter = cv2.arcLength(pts, True)
        
        # Apply Douglas-Peucker algorithm
        epsilon = epsilon_factor * perimeter
        smoothed = cv2.approxPolyDP(pts, epsilon, True)
        
        # Convert back to list format
        result = [[int(pt[0][0]), int(pt[0][1])] for pt in smoothed]
        
        print(f"🔧 Smoothed ROI: {len(points)} → {len(result)} points")
        return result
    
    @staticmethod
    def interpolate_points(points, num_points=None, spacing=None):
        """
        Add more points to ROI for smoother curves
        
        Args:
            points: List of ROI points [[x,y], ...]
            num_points: Target number of points (if specified)
            spacing: Distance between points in pixels (if specified)
            
        Returns:
            Interpolated list of points
        """
        if len(points) < 2:
            return points
        
        pts = np.array(points, dtype=np.float32)
        
        # Calculate total perimeter
        perimeter = cv2.arcLength(pts, True)
        
        # Determine number of output points
        if num_points is not None:
            n = num_points
        elif spacing is not None:
            n = max(3, int(perimeter / spacing))
        else:
            n = len(points) * 2  # Double the points by default
        
        # Create interpolation parameters
        t = np.linspace(0, 1, n, endpoint=False)
        
        # Interpolate each coordinate
        result = []
        for i in range(n):
            # Find position along perimeter
            target_dist = t[i] * perimeter
            cumulative_dist = 0
            
            for j in range(len(points)):
                p1 = points[j]
                p2 = points[(j + 1) % len(points)]
                segment_len = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                
                if cumulative_dist + segment_len >= target_dist:
                    # Interpolate on this segment
                    ratio = (target_dist - cumulative_dist) / segment_len if segment_len > 0 else 0
                    x = int(p1[0] + ratio * (p2[0] - p1[0]))
                    y = int(p1[1] + ratio * (p2[1] - p1[1]))
                    result.append([x, y])
                    break
                
                cumulative_dist += segment_len
        
        print(f"📈 Interpolated ROI: {len(points)} → {len(result)} points")
        return result if len(result) >= 3 else points

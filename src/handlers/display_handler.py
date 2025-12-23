"""
Display Handler Mixin
Contains methods for rendering overlays, toggles, and display management
"""
import cv2
import numpy as np
import math
from PyQt5.QtGui import QImage, QPixmap


class DisplayHandlerMixin:
    """Mixin class for display and rendering in MainWindow"""
    
    def _get_globals(self):
        """Get globals from integrated_main - lazy import"""
        import integrated_main
        return integrated_main
    
    def update_image(self, frame):
        """Update video display with all overlays"""
        main = self._get_globals()
        
        self.current_frame = frame.copy()
        display = frame.copy()
        
        # Update TL colors continuously (HSV pixel counting)
        self.update_tl_colors(display)
        
        # Draw direction ROIs (if enabled)
        if self.show_direction_rois and self.show_roi_overlays:
            display = self.draw_direction_rois(display)
        
        # Draw lanes (if enabled)
        if self.show_lanes:
            display = self.draw_lanes(display)
        
        # Draw stop line (if enabled)
        if getattr(self, 'show_stopline', True):
            display = self.draw_stop_line(display)
        
        # Draw temporary lane
        if main._drawing_mode == 'lane' and len(main._tmp_lane_pts) > 0:
            pts_tmp = np.array(main._tmp_lane_pts, dtype=np.int32)
            cv2.polylines(display, [pts_tmp], isClosed=False, color=(0, 255, 0), thickness=2)
            for p in main._tmp_lane_pts:
                cv2.circle(display, p, 4, (0, 255, 0), -1)
        
        # Draw temporary stop line point
        if main._drawing_mode == 'stopline' and main._tmp_stop_point is not None:
            cv2.circle(display, main._tmp_stop_point, 5, (0, 0, 255), -1)
        
        # Draw temporary direction ROI
        if main._drawing_mode == 'direction_roi' and len(main._tmp_direction_roi_pts) > 0:
            DIRECTION_COLORS = {
                'left': (0, 0, 255),
                'right': (0, 165, 255),
                'straight': (0, 255, 0)
            }
            color = DIRECTION_COLORS.get(main._selected_direction, (128, 128, 128))
            pts_tmp = np.array(main._tmp_direction_roi_pts, dtype=np.int32)
            cv2.polylines(display, [pts_tmp], isClosed=False, color=color, thickness=2)
            for p in main._tmp_direction_roi_pts:
                cv2.circle(display, tuple(p), 5, color, -1)
        
        # Draw temporary TL point
        if main._drawing_mode == 'tl_manual' and main._tmp_tl_point is not None:
            cv2.circle(display, main._tmp_tl_point, 6, (0, 200, 255), -1)
            cv2.putText(display, "P1", (main._tmp_tl_point[0]+8, main._tmp_tl_point[1]), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)
        
        # Draw reference vector (for direction calibration) - if enabled
        if getattr(self, 'show_ref_vector', True) and self.ref_vector_p1 is not None and self.ref_vector_p2 is not None:
            p1 = self.ref_vector_p1
            p2 = self.ref_vector_p2
            # Draw arrow showing reference direction
            cv2.arrowedLine(display, p1, p2, (255, 0, 255), 3, tipLength=0.05)
            # Draw start/end points
            cv2.circle(display, p1, 6, (255, 0, 255), -1)
            cv2.circle(display, p2, 6, (255, 0, 255), -1)
            # Draw label with angle
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            angle = math.degrees(math.atan2(dy, dx))
            cv2.putText(display, f"REF: {angle:.1f} deg", (mid[0] + 10, mid[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA)
        elif main._drawing_mode == 'ref_vector' and self.ref_vector_p1 is not None:
            # Show first point while waiting for second
            cv2.circle(display, self.ref_vector_p1, 6, (255, 0, 255), -1)
            cv2.putText(display, "Click second point", (self.ref_vector_p1[0] + 10, self.ref_vector_p1[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2, cv2.LINE_AA)
        
        # Overlay ALL TL ROIs and labels (if enabled)
        if getattr(self, 'show_traffic_lights', True):
            for idx, tl_data in enumerate(main.TL_ROIS):
                x1, y1, x2, y2, tl_type, current_color = tl_data
                # Color code by current light color
                box_color = (128, 128, 128)  # Gray default
                if current_color == 'đỏ':
                    box_color = (0, 0, 255)  # Red
                    color_display = "DO"
                elif current_color == 'xanh':
                    box_color = (0, 255, 0)  # Green
                    color_display = "XANH"
                elif current_color == 'vàng':
                    box_color = (0, 255, 255)  # Yellow
                    color_display = "VANG"
                else:
                    color_display = "???"
                
                # Map tl_type to ASCII for display
                if tl_type == 'tròn':
                    type_display = "tron"
                elif tl_type == 'đi thẳng':
                    type_display = "thang"
                elif tl_type == 'rẽ trái':
                    type_display = "L"
                elif tl_type == 'rẽ phải':
                    type_display = "R"
                else:
                    type_display = tl_type
                
                cv2.rectangle(display, (x1, y1), (x2, y2), box_color, 2)
                label_text = f"TL{idx+1}[{type_display}]: {color_display}"
                cv2.putText(display, label_text, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2, cv2.LINE_AA)
        
        # Convert to QImage
        rgb_image = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Scale to fit label while maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), 
            self.video_label.height(), 
            aspectRatioMode=1  # Keep aspect ratio
        )
        
        # Store scale information for accurate click detection
        self.current_display_scale = min(
            self.video_label.width() / w,
            self.video_label.height() / h
        )
        self.current_display_width = int(w * self.current_display_scale)
        self.current_display_height = int(h * self.current_display_scale)
        self.current_display_offset_x = (self.video_label.width() - self.current_display_width) // 2
        self.current_display_offset_y = (self.video_label.height() - self.current_display_height) // 2
        
        self.video_label.setPixmap(scaled_pixmap)
    
    def draw_direction_rois(self, frame):
        """Draw direction ROIs with transparency"""
        main = self._get_globals()
        
        if not main.DIRECTION_ROIS:
            return frame
        
        overlay = frame.copy()
        
        DIRECTION_COLORS = {
            'left': (0, 0, 255),      # Đỏ
            'right': (0, 165, 255),   # Vàng
            'straight': (0, 255, 0),  # Xanh
            'unknown': (128, 128, 128)
        }
        
        # Vietnamese labels without accents
        DIRECTION_LABELS = {
            'left': 'RE TRAI',
            'right': 'RE PHAI', 
            'straight': 'DI THANG',
            'unknown': 'UNKNOWN'
        }
        
        for i, roi in enumerate(main.DIRECTION_ROIS):
            pts = np.array(roi['points'], dtype=np.int32)
            color = DIRECTION_COLORS.get(roi['direction'], DIRECTION_COLORS['unknown'])
            
            # Fill polygon với độ trong suốt
            cv2.fillPoly(overlay, [pts], color)
            
            # Vẽ viền
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Vẽ label ở giữa ROI
            center_x = int(np.mean([p[0] for p in roi['points']]))
            center_y = int(np.mean([p[1] for p in roi['points']]))
            
            direction_text = DIRECTION_LABELS.get(roi['direction'], roi['direction'].upper())
            cv2.putText(frame, direction_text, (center_x - 50, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Blend overlay với frame
        alpha = 0.25
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        # Draw editing overlay if in edit mode
        if self.roi_editor.is_editing():
            roi_idx = self.roi_editor.editing_roi_index
            if roi_idx < len(main.DIRECTION_ROIS):
                points = main.DIRECTION_ROIS[roi_idx]['points']
                self.roi_editor.draw_editing_overlay(frame, points)
        
        return frame
    
    def toggle_lane_display(self):
        """Toggle lane overlay on/off"""
        self.show_lanes = self.action_toggle_lanes.isChecked()
        status = "ON" if self.show_lanes else "OFF"
        print(f"🔵 Lane display: {status}")
        self.status_label.setText(f"Status: Lane display {status}")
    
    def toggle_roi_display(self):
        """Toggle direction ROI overlay on/off"""
        self.show_roi_overlays = self.action_toggle_rois.isChecked()
        status = "ON" if self.show_roi_overlays else "OFF"
        print(f"🔵 Direction ROI display: {status}")
        self.status_label.setText(f"Status: Direction ROI display {status}")
    
    def toggle_stopline_display(self):
        """Toggle stopline overlay on/off"""
        self.show_stopline = self.action_toggle_stopline.isChecked()
        status = "ON" if self.show_stopline else "OFF"
        print(f"🔵 Stopline display: {status}")
        self.status_label.setText(f"Status: Stopline display {status}")
    
    def toggle_traffic_lights_display(self):
        """Toggle traffic lights overlay on/off"""
        self.show_traffic_lights = self.action_toggle_traffic_lights.isChecked()
        status = "ON" if self.show_traffic_lights else "OFF"
        print(f"🔵 Traffic Lights display: {status}")
        self.status_label.setText(f"Status: Traffic Lights display {status}")
    
    def toggle_ref_vector_display(self):
        """Toggle reference vector overlay on/off"""
        self.show_ref_vector = self.action_toggle_ref_vector.isChecked()
        status = "ON" if self.show_ref_vector else "OFF"
        print(f"🔵 Reference Vector display: {status}")
        self.status_label.setText(f"Status: Reference Vector display {status}")
    
    def toggle_bbox_display(self):
        """Toggle bounding box display mode"""
        main = self._get_globals()
        from PyQt5.QtWidgets import QAction
        
        # Get state from whichever control was triggered
        sender = self.sender()
        if isinstance(sender, QAction):
            # Triggered from menu - update button
            main._show_all_boxes = sender.isChecked()
            self.btn_toggle_bb.setChecked(main._show_all_boxes)
        else:
            # Triggered from button - update menu
            main._show_all_boxes = self.btn_toggle_bb.isChecked()
            self.action_toggle_boxes.setChecked(main._show_all_boxes)
        
        if main._show_all_boxes:
            self.btn_toggle_bb.setText("Show All Boxes: ON")
            self.statusBar().showMessage("Status: Showing all vehicles")
            print("📦 Showing ALL vehicle bounding boxes")
        else:
            self.btn_toggle_bb.setText("Show Only Violators: ON")
            self.statusBar().showMessage("Status: Showing only violators")
            print("🚨 Showing ONLY violator bounding boxes")

"""
Traffic Light Handler Mixin
Contains methods for traffic light ROI management
"""
import cv2
import numpy as np
from PyQt5.QtWidgets import QMessageBox, QInputDialog


class TrafficLightHandlerMixin:
    """Mixin class for traffic light handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from integrated_main - lazy import"""
        import integrated_main
        return integrated_main
    
    def update_tl_colors(self, frame):
        """Update current color for each TL ROI using HSV pixel counting - throttled to every 10 frames"""
        main = self._get_globals()
        
        if not self.tl_tracking_active or not main.TL_ROIS:
            return
        
        # Only update color every 10 frames for performance
        self.tl_color_frame_count += 1
        if self.tl_color_frame_count < 10:
            return
        self.tl_color_frame_count = 0
        
        updated_rois = []
        
        for i, roi_data in enumerate(main.TL_ROIS):
            x1, y1, x2, y2, tl_type, _ = roi_data
            roi = frame[y1:y2, x1:x2]
            
            if roi.size > 0:
                # Detect current color using HSV
                current_color = self._detect_color_hsv(roi)
                updated_rois.append((x1, y1, x2, y2, tl_type, current_color))
            else:
                updated_rois.append(roi_data)
        
        # Update global TL_ROIS
        main.TL_ROIS.clear()
        main.TL_ROIS.extend(updated_rois)
    
    def _detect_color_hsv(self, roi):
        """Detect traffic light color using HSV pixel counting"""
        try:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Define HSV ranges for red, yellow, green
            # Red (two ranges due to hue wraparound)
            red_lower1 = np.array([0, 100, 100])
            red_upper1 = np.array([10, 255, 255])
            red_lower2 = np.array([170, 100, 100])
            red_upper2 = np.array([180, 255, 255])
            
            # Yellow
            yellow_lower = np.array([20, 100, 100])
            yellow_upper = np.array([30, 255, 255])
            
            # Green
            green_lower = np.array([40, 50, 50])
            green_upper = np.array([90, 255, 255])
            
            # Count pixels
            red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
            red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
            red_count = cv2.countNonZero(red_mask1) + cv2.countNonZero(red_mask2)
            
            yellow_count = cv2.countNonZero(cv2.inRange(hsv, yellow_lower, yellow_upper))
            green_count = cv2.countNonZero(cv2.inRange(hsv, green_lower, green_upper))
            
            # Return color with most pixels
            counts = {'đỏ': red_count, 'vàng': yellow_count, 'xanh': green_count}
            max_color = max(counts, key=counts.get)
            
            # Only return if significant pixels detected
            if counts[max_color] > roi.size * 0.01:  # At least 1% of ROI
                return max_color
            return 'unknown'
            
        except Exception as e:
            return 'unknown'
    
    def find_tl_roi(self):
        """Manual TL ROI selection - click 2 points on video"""
        main = self._get_globals()
        
        if self.current_frame is None:
            self.status_label.setText("Status: No frame to select ROI from")
            return
        
        main._drawing_mode = 'tl_manual'
        main._tmp_tl_point = None
        self.status_label.setText("Status: Click 2 points to draw TL ROI")
        print("🖊️ Manual TL ROI mode - click 2 points")
        self.btn_find_tl.setText("[Selecting...] Cancel")
        self.btn_find_tl.clicked.disconnect()
        self.btn_find_tl.clicked.connect(self.cancel_tl_selection)
    
    def cancel_tl_selection(self):
        """Cancel manual TL selection"""
        main = self._get_globals()
        
        main._drawing_mode = None
        main._tmp_tl_point = None
        self.status_label.setText("Status: TL selection cancelled")
        self.btn_find_tl.setText("Add Traffic Light (Draw ROI)")
        self.btn_find_tl.clicked.disconnect()
        self.btn_find_tl.clicked.connect(self.find_tl_roi)
    
    def delete_tl(self):
        """Delete selected traffic light ROI"""
        main = self._get_globals()
        
        if len(main.TL_ROIS) == 0:
            self.status_label.setText("Status: No traffic lights to delete")
            QMessageBox.information(self, "No Traffic Lights", "No traffic lights to delete.")
            return
        
        # Show list of TLs to delete
        tl_names = [f"TL {i+1} [{tl_type}]: Position ({x1},{y1},{x2},{y2})" 
                    for i, (x1, y1, x2, y2, tl_type, _) in enumerate(main.TL_ROIS)]
        tl_name, ok = QInputDialog.getItem(
            self,
            "Delete Traffic Light",
            "Select traffic light to delete:",
            tl_names,
            editable=False
        )
        
        if ok and tl_name:
            tl_idx = tl_names.index(tl_name)
            deleted_tl = main.TL_ROIS.pop(tl_idx)
            print(f"🗑️ Deleted TL {tl_idx+1}: {deleted_tl}")
            self.status_label.setText(f"Status: Deleted TL {tl_idx+1}. {len(main.TL_ROIS)} TL(s) remaining.")
            
            # If no TLs left, disable tracking
            if len(main.TL_ROIS) == 0:
                self.tl_tracking_active = False
                print("⏹️ No TLs remaining, color tracking disabled")

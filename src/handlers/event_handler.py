"""
Event Handler Mixin
Contains mouse event handlers and keyboard shortcuts for MainWindow
"""
import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QMenu, QAction, QInputDialog


class EventHandlerMixin:
    """Mixin class for handling mouse and keyboard events in MainWindow"""
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        import integrated_main
        return integrated_main
    
    def show_context_menu(self, pos):
        """Show context menu on video area with organized actions"""
        main = self._get_globals()
        
        if self.current_frame is None:
            return
        
        menu = QMenu(self)
        
        # === DRAWING MODE Section ===
        drawing_menu = menu.addMenu("🎨 Drawing Mode")
        
        # Lane drawing
        action_draw_lane = QAction("Add Lane (polygon)", self)
        action_draw_lane.triggered.connect(self.start_add_lane)
        drawing_menu.addAction(action_draw_lane)
        
        # Stopline drawing
        action_draw_stopline = QAction("Set Stop Line (2 points)", self)
        action_draw_stopline.triggered.connect(self.start_add_stopline)
        drawing_menu.addAction(action_draw_stopline)
        
        # Traffic light
        action_draw_tl = QAction("Add Traffic Light (draw ROI)", self)
        action_draw_tl.triggered.connect(self.find_tl_roi)
        drawing_menu.addAction(action_draw_tl)
        
        # Direction ROI
        action_draw_direction = QAction("Draw Direction ROI (polygon)", self)
        action_draw_direction.triggered.connect(self.start_add_direction_roi)
        drawing_menu.addAction(action_draw_direction)
        
        # Reference vector
        drawing_menu.addSeparator()
        action_ref_vector = QAction("Set Reference Vector (2 points)", self)
        action_ref_vector.triggered.connect(self.start_set_reference_vector)
        drawing_menu.addAction(action_ref_vector)
        
        menu.addSeparator()
        
        # === EDIT MODE Section ===
        edit_menu = menu.addMenu("✏️ Edit Mode")
        
        # Edit Lane (interactive)
        action_edit_lane = QAction("Edit Lane (Interactive)", self)
        action_edit_lane.triggered.connect(self.start_edit_lane)
        action_edit_lane.setEnabled(len(main.LANE_CONFIGS) > 0)
        edit_menu.addAction(action_edit_lane)
        
        # Edit direction ROI
        action_edit_direction = QAction("Edit Direction ROI", self)
        action_edit_direction.triggered.connect(self.start_edit_direction_roi)
        action_edit_direction.setEnabled(len(main.DIRECTION_ROIS) > 0)  # Has dialog to select
        edit_menu.addAction(action_edit_direction)
        
        # Smooth ROI
        action_smooth = QAction("Smooth ROI (reduce points)", self)
        action_smooth.triggered.connect(self.smooth_current_roi)
        action_smooth.setEnabled(self.roi_editor.is_editing())  # Only during edit
        edit_menu.addAction(action_smooth)
        
        # Change directions
        action_change_dir = QAction("Change ROI Directions", self)
        action_change_dir.triggered.connect(self.change_roi_directions)
        action_change_dir.setEnabled(len(main.DIRECTION_ROIS) > 0)  # Has dialog to select
        edit_menu.addAction(action_change_dir)
        
        edit_menu.addSeparator()
        
        # Finish editing
        action_finish_edit = QAction("Finish Editing", self)
        action_finish_edit.triggered.connect(self._finish_current_editing)
        action_finish_edit.setEnabled(self.roi_editor.is_editing())  # Only during edit
        edit_menu.addAction(action_finish_edit)
        
        menu.addSeparator()
        
        # === DELETE Section ===
        delete_menu = menu.addMenu("🗑️ Delete")
        
        action_delete_lane = QAction("Delete Lane", self)
        action_delete_lane.triggered.connect(self.delete_lane)
        action_delete_lane.setEnabled(len(main.LANE_CONFIGS) > 0)  # Has dialog to select
        delete_menu.addAction(action_delete_lane)
        
        action_delete_stopline = QAction("Delete Stop Line", self)
        action_delete_stopline.triggered.connect(self.delete_stopline)
        action_delete_stopline.setEnabled(main.STOP_LINE is not None)
        delete_menu.addAction(action_delete_stopline)
        
        action_delete_tl = QAction("Delete Traffic Light", self)
        action_delete_tl.triggered.connect(self.delete_tl)
        action_delete_tl.setEnabled(len(main.TL_ROIS) > 0)  # Has dialog to select
        delete_menu.addAction(action_delete_tl)
        
        action_delete_direction = QAction("Delete Direction ROI", self)
        action_delete_direction.triggered.connect(self.delete_direction_roi)
        action_delete_direction.setEnabled(len(main.DIRECTION_ROIS) > 0)  # Has dialog to select
        delete_menu.addAction(action_delete_direction)
        
        menu.addSeparator()
        
        # === VIEW Section ===
        view_menu = menu.addMenu("👁️ View Options")
        
        # Toggle direction ROIs
        action_toggle_dir = QAction("Toggle Direction ROIs", self)
        action_toggle_dir.setCheckable(True)
        action_toggle_dir.setChecked(self.show_direction_rois)
        action_toggle_dir.triggered.connect(self.toggle_direction_rois)
        view_menu.addAction(action_toggle_dir)
        
        # Toggle all boxes
        action_toggle_boxes = QAction("Show All Bounding Boxes", self)
        action_toggle_boxes.setCheckable(True)
        action_toggle_boxes.setChecked(main._show_all_boxes)
        action_toggle_boxes.triggered.connect(self.toggle_bbox_display)
        view_menu.addAction(action_toggle_boxes)
        
        menu.addSeparator()
        
        # === CONFIG Section ===
        config_menu = menu.addMenu("💾 Configuration")
        
        action_save_config = QAction("Save All ROIs Configuration", self)
        action_save_config.triggered.connect(self.save_configuration)
        config_menu.addAction(action_save_config)
        
        action_load_config = QAction("Load Configuration", self)
        action_load_config.triggered.connect(self.load_configuration)
        config_menu.addAction(action_load_config)
        
        # Show menu at cursor position
        menu.exec_(self.video_label.mapToGlobal(pos))
    
    def video_mouse_press(self, event):
        """Handle mouse press events on video label"""
        main = self._get_globals()
        
        if self.current_frame is None:
            return
        
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QMessageBox
        
        # Use stored scale information for accurate click detection
        if not hasattr(self, 'current_display_scale'):
            return
        
        # Get click position relative to label
        click_x = event.pos().x() - self.current_display_offset_x
        click_y = event.pos().y() - self.current_display_offset_y
        
        # Convert to frame coordinates using stored scale
        if 0 <= click_x < self.current_display_width and 0 <= click_y < self.current_display_height:
            frame_x = int(click_x / self.current_display_scale)
            frame_y = int(click_y / self.current_display_scale)
            
            # Handle lane editing mode
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                lane = main.LANE_CONFIGS[self.editing_lane_idx]
                points = lane['poly']
                
                # Right-click to delete point
                if event.button() == Qt.RightButton:
                    for i, (px, py) in enumerate(points):
                        dist = ((frame_x - px)**2 + (frame_y - py)**2) ** 0.5
                        if dist < 15:  # Within 15 pixels
                            if len(points) <= 3:
                                QMessageBox.warning(self, "Minimum Points", "Lane must have at least 3 points!")
                                return
                            del points[i]
                            self.update_lists()
                            print(f"🗑️ Deleted point {i+1} from Lane {self.editing_lane_idx+1}")
                            return
                    return
                
                # Left-click to start dragging
                if event.button() == Qt.LeftButton:
                    for i, (px, py) in enumerate(points):
                        dist = ((frame_x - px)**2 + (frame_y - py)**2) ** 0.5
                        if dist < 15:  # Within 15 pixels
                            self.dragging_lane_point_idx = i
                            print(f"🖱️ Started dragging point {i+1}")
                            return
                    
                    # If not dragging, reset
                    self.dragging_lane_point_idx = None
                return
            
            # Handle ROI editing mode (both lanes and direction ROIs)
            if self.roi_editor.is_editing():
                roi_idx = self.roi_editor.editing_roi_index
                button_name = 'right' if event.button() == Qt.RightButton else 'left'
                
                if self.roi_editor.is_editing_lane():
                    # Editing a lane
                    if roi_idx < len(main.LANE_CONFIGS):
                        points = main.LANE_CONFIGS[roi_idx]['poly']
                        self.roi_editor.handle_mouse_press(frame_x, frame_y, button_name, points)
                elif self.roi_editor.is_editing_direction():
                    # Editing a direction ROI
                    if roi_idx < len(main.DIRECTION_ROIS):
                        points = main.DIRECTION_ROIS[roi_idx]['points']
                        self.roi_editor.handle_mouse_press(frame_x, frame_y, button_name, points)
                return
            
            if main._drawing_mode == 'lane':
                main._tmp_lane_pts.append((frame_x, frame_y))
                print(f"📍 Điểm {len(main._tmp_lane_pts)} của lane: ({frame_x}, {frame_y})")
            elif main._drawing_mode == 'stopline':
                if main._tmp_stop_point is None:
                    main._tmp_stop_point = (frame_x, frame_y)
                    print(f"📍 Điểm đầu vạch dừng: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click second point for THE stop line")
                else:
                    p1 = main._tmp_stop_point
                    p2 = (frame_x, frame_y)
                    main.STOP_LINE = (p1, p2)
                    print(f"🚦 Đã tạo vạch dừng: {p1} -> {p2}")
                    main._tmp_stop_point = None
                    main._drawing_mode = None
                    self.status_label.setText("Status: Stopline created. Direction tracking enabled.")
            elif main._drawing_mode == 'direction_roi':
                # Add point to direction ROI
                main._tmp_direction_roi_pts.append([frame_x, frame_y])
                print(f"📍 Direction ROI point {len(main._tmp_direction_roi_pts)}: ({frame_x}, {frame_y})")
                self.status_label.setText(f"Status: Direction ROI - {len(main._tmp_direction_roi_pts)} points. Click 'Finish' when done.")
            elif main._drawing_mode == 'ref_vector':
                # Reference vector for camera nghiêng
                if self.ref_vector_p1 is None:
                    self.ref_vector_p1 = (frame_x, frame_y)
                    print(f"📍 Ref Vector P1: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click END point on straight lane")
                elif self.ref_vector_p2 is None:
                    self.ref_vector_p2 = (frame_x, frame_y)
                    print(f"📍 Ref Vector P2: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click 'Finish Reference Vector'")
            elif main._drawing_mode == 'tl_manual':
                if main._tmp_tl_point is None:
                    main._tmp_tl_point = (frame_x, frame_y)
                    print(f"📍 TL ROI điểm 1: ({frame_x}, {frame_y})")
                    self.status_label.setText("Status: Click second point for TL ROI")
                else:
                    p1 = main._tmp_tl_point
                    p2 = (frame_x, frame_y)
                    x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
                    x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
                    
                    # Ask user to select TL type
                    tl_types = ['đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải']
                    tl_type, ok = QInputDialog.getItem(
                        self,
                        "Select Traffic Light Type",
                        "Chọn loại đèn giao thông:",
                        tl_types,
                        editable=False
                    )
                    
                    if not ok:
                        # User cancelled - reset
                        main._tmp_tl_point = None
                        main._drawing_mode = None
                        self.status_label.setText("Status: TL selection cancelled")
                        return
                    
                    # Add to list with 6-tuple format (position + type + color) - NO stoplines
                    main.TL_ROIS.append((x1, y1, x2, y2, tl_type, 'unknown'))
                    print(f"🚦 TL ROI created: ({x1},{y1},{x2},{y2}) Type={tl_type}")
                    print(f"📍 Use vehicle direction to match with TL type")
                    
                    # Enable color tracking
                    self.tl_tracking_active = True
                    print("🚦 HSV color tracking started")
                    
                    main._tmp_tl_point = None
                    main._drawing_mode = None
                    
                    self.status_label.setText(f"Status: TL {len(main.TL_ROIS)} added ({tl_type}). Total: {len(main.TL_ROIS)} TL(s)")
                    self.btn_find_tl.setText("Add Traffic Light")
                    self.btn_find_tl.clicked.disconnect()
                    self.btn_find_tl.clicked.connect(self.find_tl_roi)
    
    def video_mouse_move(self, event):
        """Handle mouse move for dragging points and hover effects"""
        main = self._get_globals()
        
        if self.current_frame is None:
            return
        
        # Get mouse position in frame coordinates
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        frame_height, frame_width = self.current_frame.shape[:2]
        
        scale = min(label_width / frame_width, label_height / frame_height)
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
        offset_x = (label_width - display_width) // 2
        offset_y = (label_height - display_height) // 2
        
        mouse_x = event.pos().x() - offset_x
        mouse_y = event.pos().y() - offset_y
        
        if 0 <= mouse_x < display_width and 0 <= mouse_y < display_height:
            frame_x = int(mouse_x / scale)
            frame_y = int(mouse_y / scale)
            
            # Handle lane editing drag
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                if hasattr(self, 'dragging_lane_point_idx') and self.dragging_lane_point_idx is not None:
                    lane = main.LANE_CONFIGS[self.editing_lane_idx]
                    lane['poly'][self.dragging_lane_point_idx] = [frame_x, frame_y]
                    self.update_lists()
                return
            
            # Handle ROI editing (both lanes and direction ROIs)
            if not self.roi_editor.is_editing():
                return
            
            roi_idx = self.roi_editor.editing_roi_index
            if self.roi_editor.is_editing_lane():
                if roi_idx < len(main.LANE_CONFIGS):
                    points = main.LANE_CONFIGS[roi_idx]['poly']
                    self.roi_editor.handle_mouse_move(frame_x, frame_y, points)
            elif self.roi_editor.is_editing_direction():
                if roi_idx < len(main.DIRECTION_ROIS):
                    points = main.DIRECTION_ROIS[roi_idx]['points']
                    self.roi_editor.handle_mouse_move(frame_x, frame_y, points)
    
    def video_mouse_release(self, event):
        """Stop dragging point"""
        # Stop lane point dragging
        if hasattr(self, 'dragging_lane_point_idx'):
            if self.dragging_lane_point_idx is not None:
                print(f"✅ Finished dragging point {self.dragging_lane_point_idx + 1}")
            self.dragging_lane_point_idx = None
        
        # Stop ROI point dragging
        self.roi_editor.handle_mouse_release()
    
    def video_mouse_double_click(self, event):
        """Double-click on edge to insert new point"""
        main = self._get_globals()
        from PyQt5.QtCore import Qt
        
        if event.button() != Qt.LeftButton:
            return
        
        if self.current_frame is None:
            return
        
        # Get click position in frame coordinates
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        frame_height, frame_width = self.current_frame.shape[:2]
        
        scale = min(label_width / frame_width, label_height / frame_height)
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
        offset_x = (label_width - display_width) // 2
        offset_y = (label_height - display_height) // 2
        
        click_x = event.pos().x() - offset_x
        click_y = event.pos().y() - offset_y
        
        if 0 <= click_x < display_width and 0 <= click_y < display_height:
            frame_x = int(click_x / scale)
            frame_y = int(click_y / scale)
            
            # Handle lane editing - double click to add point
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                lane = main.LANE_CONFIGS[self.editing_lane_idx]
                points = lane['poly']
                
                # Find closest edge to insert new point
                min_dist = float('inf')
                insert_idx = None
                
                for i in range(len(points)):
                    p1 = points[i]
                    p2 = points[(i + 1) % len(points)]
                    dist = self._point_to_segment_dist(frame_x, frame_y, p1[0], p1[1], p2[0], p2[1])
                    if dist < min_dist:
                        min_dist = dist
                        insert_idx = i + 1
                
                if min_dist < 30:  # Within 30 pixels of edge
                    points.insert(insert_idx, [frame_x, frame_y])
                    self.update_lists()
                    print(f"➕ Added new point at position {insert_idx+1}")
                return
            
            # Handle ROI editing (both lanes and direction ROIs)
            if not self.roi_editor.is_editing():
                return
            
            roi_idx = self.roi_editor.editing_roi_index
            if self.roi_editor.is_editing_lane():
                if roi_idx < len(main.LANE_CONFIGS):
                    points = main.LANE_CONFIGS[roi_idx]['poly']
                    if self.roi_editor.handle_double_click(frame_x, frame_y, points):
                        self.update_lists()
            elif self.roi_editor.is_editing_direction():
                if roi_idx < len(main.DIRECTION_ROIS):
                    points = main.DIRECTION_ROIS[roi_idx]['points']
                    if self.roi_editor.handle_double_click(frame_x, frame_y, points):
                        self.update_direction_roi_list()
    
    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point to line segment"""
        import numpy as np
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1)**2 + (py - y1)**2)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return np.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for finishing drawings"""
        main = self._get_globals()
        from PyQt5.QtCore import Qt
        
        # Enter/Return key to finish drawing or editing
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Debug
            print(f"🔍 keyPressEvent Enter: is_editing={self.roi_editor.is_editing()}, "
                  f"is_editing_lane={self.roi_editor.is_editing_lane()}, "
                  f"is_editing_direction={self.roi_editor.is_editing_direction()}, "
                  f"editing_type={self.roi_editor.editing_type}")
            
            # Finish lane editing via roi_editor
            if hasattr(self, 'roi_editor') and self.roi_editor.is_editing_lane():
                print("📌 KeyPress: Calling finish_edit_lane()")
                self.finish_edit_lane()
                return
            # Finish direction ROI editing via roi_editor
            if hasattr(self, 'roi_editor') and self.roi_editor.is_editing_direction():
                print("📌 KeyPress: Calling finish_edit_roi()")
                self.finish_edit_roi()
                return
            # Legacy: Finish lane editing
            if hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
                self.finish_edit_lane()
                return
            if main._drawing_mode == 'lane':
                # Finish lane drawing
                self.finish_lane()
                return
            elif main._drawing_mode == 'direction_roi':
                # Finish direction ROI drawing
                self.finish_direction_roi()
                return
            elif main._drawing_mode == 'ref_vector':
                # Finish reference vector
                self.finish_reference_vector()
                return
        
        # Call parent class handler for other keys
        from PyQt5.QtWidgets import QMainWindow
        super(QMainWindow, self).keyPressEvent(event)

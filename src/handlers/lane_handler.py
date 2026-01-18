"""
Lane Handler Mixin
Contains methods for lane and stopline management
"""
import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel


class LaneHandlerMixin:
    """Mixin class for lane and stopline handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        import integrated_main
        return integrated_main
    
    # ========================================================================
    # Lane Drawing Methods
    # ========================================================================
    
    def start_add_lane(self):
        """Start lane drawing mode"""
        main = self._get_globals()
        main._drawing_mode = 'lane'
        main._tmp_lane_pts = []
        self.status_label.setText("Status: Click on video to draw lane. Press 'Finish Lane' or ENTER when done.")
        self.btn_add_lane.setText("Finish Lane (n)")
        self.btn_add_lane.clicked.disconnect()
        self.btn_add_lane.clicked.connect(self.finish_lane)
        
    def finish_lane(self):
        """Finish drawing and save lane"""
        main = self._get_globals()
        
        if len(main._tmp_lane_pts) < 3:
            self.status_label.setText("Status: Need at least 3 points for a lane")
            return
            
        poly = main._tmp_lane_pts.copy()
        print(f"✅ Created lane with {len(poly)} points")
        
        # Show vehicle type dialog
        from ui.lane_selector import VehicleTypeDialog
        dialog = VehicleTypeDialog(self)
        if dialog.exec_() == dialog.Accepted:
            allowed = dialog.get_selected()
            main.LANE_CONFIGS.append({
                "poly": poly,
                "points": poly,  # Also save as points for config compatibility
                "label": f"Lane {len(main.LANE_CONFIGS) + 1}",
                "allowed_types": allowed,  # Primary key for video_thread
                "allowed_labels": allowed  # Also set for compatibility
            })
            self.status_label.setText(f"Status: Lane added with vehicles: {', '.join(allowed)}")
        
        main._tmp_lane_pts = []
        main._drawing_mode = None
        self.btn_add_lane.setText("Add Lane (Click on video)")
        self.btn_add_lane.clicked.disconnect()
        self.btn_add_lane.clicked.connect(self.start_add_lane)
        self.update_lists()
    
    # ========================================================================
    # Stopline Methods
    # ========================================================================
        
    def start_add_stopline(self):
        """Start stopline drawing mode"""
        main = self._get_globals()
        
        if main.STOP_LINE is not None:
            reply = QMessageBox.question(
                self,
                "Replace Stopline?",
                "Chỉ được có 1 vạch dừng. Bạn có muốn thay thế vạch cũ không?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Reset lane drawing if in progress
        if main._drawing_mode == 'lane':
            main._tmp_lane_pts = []
            self.btn_add_lane.setText("Add Lane (Click on video)")
            self.btn_add_lane.clicked.disconnect()
            self.btn_add_lane.clicked.connect(self.start_add_lane)
        
        main._drawing_mode = 'stopline'
        main._tmp_stop_point = None
        self.status_label.setText("Status: Click 2 points for THE stop line")
        
    def delete_stopline(self):
        """Delete current stopline"""
        main = self._get_globals()
        
        if main.STOP_LINE is None:
            self.status_label.setText("Status: No stopline to delete")
            QMessageBox.information(self, "No Stopline", "No stopline to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Stopline?",
            "Xóa vạch dừng?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            main.STOP_LINE = None
            self.status_label.setText("Status: Stopline deleted")
            print("🗑️ Stopline deleted")
    
    # ========================================================================
    # Lane Edit Methods (Interactive editing like ROI editor)
    # ========================================================================
    
    def start_edit_lane(self):
        """Start interactive lane editing - drag/add/delete keypoints using ROI editor"""
        main = self._get_globals()
        
        # Check if lanes exist
        if not main.LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes configured yet. Please add lanes first.")
            return
        
        # Show selection dialog
        selection_dialog = QDialog(self)
        selection_dialog.setWindowTitle("Select Lane to Edit")
        selection_dialog.setMinimumSize(400, 300)
        sel_layout = QVBoxLayout(selection_dialog)
        
        sel_layout.addWidget(QLabel("<b>Select a lane to edit:</b>"))
        sel_lane_list = QListWidget()
        for idx, lane in enumerate(main.LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            points = lane.get('poly', [])
            sel_lane_list.addItem(f"Lane {idx}: {len(points)} points - Allowed: {', '.join(allowed)}")
        sel_layout.addWidget(sel_lane_list)
        
        # Select first item by default
        if sel_lane_list.count() > 0:
            sel_lane_list.setCurrentRow(0)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Edit")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        sel_layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(selection_dialog.reject)
        
        def on_ok():
            sel_idx = sel_lane_list.currentRow()
            if sel_idx >= 0:
                selection_dialog.selected_idx = sel_idx
                selection_dialog.accept()
            else:
                QMessageBox.warning(selection_dialog, "No Selection", "Please select a lane!")
        
        btn_ok.clicked.connect(on_ok)
        
        if selection_dialog.exec_() == QDialog.Rejected:
            return
        
        selected = getattr(selection_dialog, 'selected_idx', -1)
        if selected < 0:
            return
        
        lane = main.LANE_CONFIGS[selected]
        
        # Start ROI editor in lane mode
        if hasattr(self, 'roi_editor'):
            self.roi_editor.start_editing(selected, roi_type='lane')
            
            # Enable finish button
            if hasattr(self, 'btn_finish_edit_roi'):
                self.btn_finish_edit_roi.setEnabled(True)
            if hasattr(self, 'action_finish_edit'):
                self.action_finish_edit.setEnabled(True)
            
            self.status_label.setText(
                f"Status: Editing Lane {selected+1} - {len(lane['poly'])} points | "
                f"Left-click+drag=move | Double-click=add | Right-click=delete | Press Enter to finish"
            )
            
            print(f"✏️ Started editing Lane {selected+1}: ({len(lane['poly'])} points)")
            print(f"   Left-click and drag to move points")
            print(f"   Double-click near edge to add new point")
            print(f"   Right-click on point to delete it")
        else:
            QMessageBox.warning(self, "Editor Not Available", "ROI editor not initialized.")
    
    def finish_edit_lane(self):
        """Finish lane editing and show vehicle type selection dialog"""
        main = self._get_globals()
        from PyQt5.QtWidgets import QCheckBox
        
        # Check if we're editing a lane using roi_editor
        if hasattr(self, 'roi_editor') and self.roi_editor.is_editing_lane():
            selected = self.roi_editor.editing_roi_index
        elif hasattr(self, 'editing_lane_idx') and self.editing_lane_idx is not None:
            selected = self.editing_lane_idx
        else:
            return
        
        if selected < 0 or selected >= len(main.LANE_CONFIGS):
            return
            
        lane = main.LANE_CONFIGS[selected]
        
        # Stop editing mode
        if hasattr(self, 'roi_editor'):
            self.roi_editor.finish_editing()
        self.editing_lane_idx = None
        self.dragging_lane_point_idx = None
        
        # Disable finish edit button
        if hasattr(self, 'btn_finish_edit_roi'):
            self.btn_finish_edit_roi.setEnabled(False)
        
        # Show vehicle type selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Configure Lane {selected + 1}")
        dialog.setMinimumSize(350, 250)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("<b>Select Allowed Vehicle Types:</b>"))
        
        allowed = lane.get('allowed_labels', ['all'])
        
        check_all = QCheckBox("All vehicles")
        check_all.setChecked('all' in allowed)
        layout.addWidget(check_all)
        
        check_xe_may = QCheckBox("Xe máy")
        check_xe_may.setChecked('xe may' in allowed)
        layout.addWidget(check_xe_may)
        
        check_o_to = QCheckBox("Ô tô")
        check_o_to.setChecked('o to' in allowed)
        layout.addWidget(check_o_to)
        
        check_xe_bus = QCheckBox("Xe bus")
        check_xe_bus.setChecked('xe bus' in allowed)
        layout.addWidget(check_xe_bus)
        
        check_xe_tai = QCheckBox("Xe tải")
        check_xe_tai.setChecked('xe tai' in allowed)
        layout.addWidget(check_xe_tai)
        
        # Save/Cancel buttons
        button_box = QHBoxLayout()
        btn_save = QPushButton("Save Changes")
        btn_cancel = QPushButton("Cancel")
        button_box.addWidget(btn_save)
        button_box.addWidget(btn_cancel)
        layout.addLayout(button_box)
        
        def save_changes():
            new_allowed = []
            if check_all.isChecked():
                new_allowed = ['all']
            else:
                if check_xe_may.isChecked():
                    new_allowed.append('xe may')
                if check_o_to.isChecked():
                    new_allowed.append('o to')
                if check_xe_bus.isChecked():
                    new_allowed.append('xe bus')
                if check_xe_tai.isChecked():
                    new_allowed.append('xe tai')
            
            if not new_allowed:
                QMessageBox.warning(dialog, "No Selection", "Please select at least one vehicle type or 'All'")
                return
            
            # Update both keys for compatibility
            lane['allowed_labels'] = new_allowed
            lane['allowed_types'] = new_allowed
            
            self.update_lists()
            print(f"✅ Lane {selected + 1} configured: Allowed vehicles = {new_allowed}")
            dialog.accept()
        
        btn_save.clicked.connect(save_changes)
        btn_cancel.clicked.connect(dialog.reject)
        
        # Update status
        self.status_label.setText("Status: Ready")
        
        dialog.exec_()

    # ========================================================================
    # Lane Management Methods
    # ========================================================================
            
    def delete_lane(self):
        """Delete lane with selection dialog"""
        main = self._get_globals()
        
        if not main.LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes to delete.")
            return
        
        # Show selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete Lane")
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("<b>Select a lane to delete:</b>"))
        lane_list_widget = QListWidget()
        for idx, lane in enumerate(main.LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            points = lane.get('poly', [])
            lane_list_widget.addItem(f"Lane {idx}: {len(points)} points - Allowed: {', '.join(allowed)}")
        layout.addWidget(lane_list_widget)
        
        # Select first item by default
        if lane_list_widget.count() > 0:
            lane_list_widget.setCurrentRow(0)
        
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("Delete")
        btn_delete.setStyleSheet("background-color: #dc3545; color: white;")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(dialog.reject)
        
        def on_delete():
            sel_idx = lane_list_widget.currentRow()
            if sel_idx >= 0 and sel_idx < len(main.LANE_CONFIGS):
                del main.LANE_CONFIGS[sel_idx]
                self.update_lists()
                self.status_label.setText(f"Status: Deleted Lane {sel_idx + 1}")
                print(f"🗑️ Deleted Lane {sel_idx + 1}")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a lane to delete.")
        
        btn_delete.clicked.connect(on_delete)
        dialog.exec_()
    
    # show_edit_lane_dialog removed - use start_edit_lane instead
    
    def delete_selected_lane(self, lane_idx, dialog):
        """Delete the selected lane from dialog"""
        main = self._get_globals()
        
        if lane_idx < 0 or lane_idx >= len(main.LANE_CONFIGS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a lane to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete Lane {lane_idx + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del main.LANE_CONFIGS[lane_idx]
            print(f"🗑️ Lane {lane_idx + 1} deleted")
            self.status_label.setText(f"Status: Lane {lane_idx + 1} deleted. Total: {len(main.LANE_CONFIGS)}")
            dialog.close()
    
    # ========================================================================
    # Drawing Methods
    # ========================================================================
    
    def draw_lanes(self, frame):
        """Draw lane overlays on frame"""
        main = self._get_globals()
        
        overlay = frame.copy()
        for idx, lane in enumerate(main.LANE_CONFIGS, start=1):
            poly = lane["poly"]
            pts = np.array(poly, dtype=np.int32)
            cv2.fillPoly(overlay, [pts], (0, 255, 255))
            cv2.polylines(overlay, [pts], isClosed=True, color=(0, 200, 200), thickness=2)
            cx = int(sum(p[0] for p in poly) / len(poly))
            cy = int(sum(p[1] for p in poly) / len(poly))
            cv2.putText(overlay, f"L{idx}", (cx-15, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        alpha = 0.3
        out = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        return out
    
    def draw_stop_line(self, frame):
        """Draw THE stop line on frame"""
        main = self._get_globals()
        
        if main.STOP_LINE is not None:
            p1, p2 = main.STOP_LINE
            cv2.line(frame, p1, p2, (0, 0, 255), 4)
            cv2.putText(frame, "STOP LINE", (p1[0], p1[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame
    
    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point to line segment"""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1)**2 + (py - y1)**2)
        t = max(0, min(1, ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return np.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    def show_edit_lane_vehicle_types_dialog(self):
        """Show dialog to edit only vehicle types (without keypoints)"""
        main = self._get_globals()
        
        if not main.LANE_CONFIGS:
            QMessageBox.information(self, "No Lanes", "No lanes configured yet. Please add lanes first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Lane Vehicle Types")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Lane list
        lane_list = QListWidget()
        for idx, lane in enumerate(main.LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', lane.get('allowed_types', ['all']))
            lane_list.addItem(f"Lane {idx}: {', '.join(allowed)}")
        
        # Select first by default
        if lane_list.count() > 0:
            lane_list.setCurrentRow(0)
        
        layout.addWidget(QLabel("<b>Select a lane to edit:</b>"))
        layout.addWidget(lane_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Edit Vehicle Types")
        btn_edit.clicked.connect(lambda: self._edit_lane_vehicle_types(lane_list.currentRow(), dialog))
        btn_layout.addWidget(btn_edit)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def _edit_lane_vehicle_types(self, lane_idx, dialog):
        """Edit vehicle types for a specific lane"""
        main = self._get_globals()
        
        if lane_idx < 0 or lane_idx >= len(main.LANE_CONFIGS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a lane to edit.")
            return
        
        # Show vehicle type dialog
        from ui.lane_selector import VehicleTypeDialog
        vehicle_dialog = VehicleTypeDialog(self)
        
        # Pre-select current allowed types
        current_allowed = main.LANE_CONFIGS[lane_idx].get('allowed_labels', [])
        vehicle_dialog.set_selected(current_allowed)
        
        if vehicle_dialog.exec_() == vehicle_dialog.Accepted:
            allowed = vehicle_dialog.get_selected()
            main.LANE_CONFIGS[lane_idx]['allowed_labels'] = allowed
            main.LANE_CONFIGS[lane_idx]['allowed_types'] = allowed
            print(f"✏️ Lane {lane_idx + 1} updated: {', '.join(allowed)}")
            self.status_label.setText(f"Status: Lane {lane_idx + 1} updated")
            dialog.close()
            self.update_lists()

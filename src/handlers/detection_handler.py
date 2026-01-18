"""
Detection Handler Mixin - Handles detection start/stop and ROI editing dialogs
"""
import sys
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton


def _get_globals():
    """Get globals from the main module - handles both __main__ and integrated_main cases"""
    if '__main__' in sys.modules:
        main_module = sys.modules['__main__']
        if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
            return main_module
    import integrated_main
    return integrated_main


class DetectionHandlerMixin:
    """Mixin class for detection control and ROI editing functionality"""
    
    def show_edit_roi_dialog(self):
        """Show dialog to select and edit a direction ROI"""
        g = _get_globals()
        DIRECTION_ROIS = g.DIRECTION_ROIS
        
        if not DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No direction ROIs configured yet. Please add ROIs first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Direction ROI")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # ROI list
        roi_list = QListWidget()
        for idx, roi in enumerate(DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            secondary_dirs = roi.get('secondary_directions', [])
            allowed_dirs = [primary_dir] + [d.upper() for d in secondary_dirs]
            points = roi.get('points', [])
            roi_list.addItem(f"ROI {idx}: {', '.join(allowed_dirs)} - {len(points)} points")
        
        layout.addWidget(QLabel("<b>Select a direction ROI to edit:</b>"))
        layout.addWidget(roi_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_edit = QPushButton("Edit Selected")
        btn_edit.clicked.connect(lambda: self.start_edit_selected_roi(roi_list.currentRow(), dialog))
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(lambda: self.delete_selected_roi(roi_list.currentRow(), dialog))
        btn_layout.addWidget(btn_delete)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec_()
    
    def start_edit_selected_roi(self, roi_idx, dialog):
        """Start editing the selected direction ROI"""
        g = _get_globals()
        DIRECTION_ROIS = g.DIRECTION_ROIS
        
        if roi_idx < 0 or roi_idx >= len(DIRECTION_ROIS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a ROI to edit.")
            return
        
        dialog.close()
        
        # Start ROI editor
        self.roi_editor.start_editing(roi_idx)
        self.action_smooth_roi.setEnabled(True)
        self.action_change_directions.setEnabled(True)
        self.action_finish_edit.setEnabled(True)
        
        print(f"✏️ Editing Direction ROI {roi_idx + 1}")
        self.status_label.setText(f"Status: Editing ROI {roi_idx + 1} - Drag points to adjust")

    def delete_selected_roi(self, roi_idx, dialog):
        """Delete the selected direction ROI"""
        g = _get_globals()
        DIRECTION_ROIS = g.DIRECTION_ROIS
        
        if roi_idx < 0 or roi_idx >= len(DIRECTION_ROIS):
            QMessageBox.warning(self, "Invalid Selection", "Please select a ROI to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete Direction ROI {roi_idx + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del DIRECTION_ROIS[roi_idx]
            print(f"🗑️ Direction ROI {roi_idx + 1} deleted")
            self.status_label.setText(f"Status: ROI {roi_idx + 1} deleted. Total: {len(DIRECTION_ROIS)}")
            dialog.close()
    
    def update_lists(self):
        """Update lane and direction ROI list widgets"""
        g = _get_globals()
        LANE_CONFIGS = g.LANE_CONFIGS
        
        self.lane_list.clear()
        for idx, lane in enumerate(LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            self.lane_list.addItem(f"Lane {idx}: {len(lane['poly'])} points - {', '.join(allowed)}")
        
        # Update direction ROI list
        self.update_direction_roi_list()
            
    def start_detection(self):
        """Start or stop vehicle detection"""
        g = _get_globals()
        DIRECTION_ROIS = g.DIRECTION_ROIS
        VIOLATOR_TRACK_IDS = g.VIOLATOR_TRACK_IDS
        RED_LIGHT_VIOLATORS = g.RED_LIGHT_VIOLATORS
        LANE_VIOLATORS = g.LANE_VIOLATORS
        DIRECTION_VIOLATORS = g.DIRECTION_VIOLATORS
        PASSED_VEHICLES = g.PASSED_VEHICLES
        MOTORBIKE_COUNT = g.MOTORBIKE_COUNT
        CAR_COUNT = g.CAR_COUNT
        
        if not g._detection_running:
            # Debug: Check prerequisites
            print(f"🔍 Debug - yolo_model: {self.yolo_model is not None}")
            print(f"🔍 Debug - thread exists: {hasattr(self, 'thread')}")
            if hasattr(self, 'thread'):
                print(f"🔍 Debug - thread.model: {self.thread.model is not None}")
                print(f"🔍 Debug - thread.model_loaded: {self.thread.model_loaded}")
            
            if self.yolo_model is None:
                self.status_label.setText("Status: Model not loaded at startup")
                QMessageBox.warning(self, "No Model", "Please select a model first!")
                print("❌ Detection failed: yolo_model is None")
                return
            
            # Check if reference vector is set (critical for direction detection accuracy)
            if self.ref_vector_p1 is None or self.ref_vector_p2 is None:
                if DIRECTION_ROIS:  # Only warn if direction ROIs exist
                    reply = QMessageBox.question(
                        self,
                        "⚠️ Reference Vector Not Set",
                        "Reference Vector chưa được thiết lập để xác định hướng thẳng.\n\n"
                        "Điều này CÓ THỂ ẢNH HƯỞNG ĐỘ CHÍNH XÁC khi:\n"
                        "- Phát hiện xe rẽ trái/phải\n"
                        "- Xác định vi phạm đèn tín hiệu theo hướng\n\n"
                        "⚠️ Khuyến nghị: Set Reference Vector trước khi start detection\n"
                        "(Click 'Set Reference Vector' và chọn 2 điểm theo hướng thẳng)\n\n"
                        "Bạn có muốn tiếp tục KHÔNG CÓ Reference Vector?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        self.status_label.setText("Status: Please set Reference Vector first")
                        return
            
            # Pass pre-loaded model to thread
            if not self.thread.model_loaded:
                self.thread.set_model(self.yolo_model)
                self.thread.model_config = self.current_model_config
            
            self.thread.detection_enabled = True
            g._detection_running = True
            self.btn_start.setText("Stop Detection")
            self.action_start_detection.setText("Stop Detection")
            self.status_label.setText("Status: Detection running...")
            print("🚀 Detection started")
        else:
            self.thread.detection_enabled = False
            g._detection_running = False
            self.btn_start.setText("Start Detection")
            self.action_start_detection.setText("Start Detection")
            self.status_label.setText("Status: Detection stopped")
            print("⏹️ Detection stopped")
            VIOLATOR_TRACK_IDS.clear()
            RED_LIGHT_VIOLATORS.clear()
            LANE_VIOLATORS.clear()
            DIRECTION_VIOLATORS.clear()
            PASSED_VEHICLES.clear()
            MOTORBIKE_COUNT.clear()
            CAR_COUNT.clear()

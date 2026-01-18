"""
Direction ROI Handler Mixin
Contains all methods related to direction ROI management for MainWindow

NOTE: This mixin uses global variables from integrated_main module:
- DIRECTION_ROIS
- _selected_direction
- _drawing_mode
- _tmp_direction_roi_pts
"""
import sys
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QDialog, QVBoxLayout, QCheckBox, 
    QDialogButtonBox, QLabel, QRadioButton, QButtonGroup, QInputDialog, QAction,
    QListWidget, QHBoxLayout, QPushButton
)


class DirectionROIHandlerMixin:
    """Mixin class containing direction ROI handling methods for MainWindow
    
    Uses global variables from integrated_main module via lazy import to avoid circular imports.
    """
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        import integrated_main
        return integrated_main
    
    def on_direction_changed(self, direction):
        """Called when user selects direction from dropdown"""
        main = self._get_globals()
        main._selected_direction = direction
        print(f"🎯 Selected direction: {direction.upper()}")
        self.status_label.setText(f"Status: Direction set to {direction.upper()}")
    
    def start_add_direction_roi(self):
        """Start drawing direction ROI"""
        main = self._get_globals()
        
        if self.current_frame is None:
            QMessageBox.warning(self, "No Frame", "No video frame available. Please load a video first.")
            return
        
        main._drawing_mode = 'direction_roi'
        main._tmp_direction_roi_pts = []
        self.btn_finish_direction_roi.setEnabled(True)
        self.status_label.setText(f"Status: Click points to draw {main._selected_direction.upper()} ROI. Click 'Finish' or press ENTER when done.")
        print(f"🖊️ Drawing Direction ROI: {main._selected_direction.upper()}")
    
    def finish_direction_roi(self):
        """Finish drawing current direction ROI"""
        main = self._get_globals()
        
        if len(main._tmp_direction_roi_pts) < 3:
            QMessageBox.warning(self, "Invalid ROI", "Direction ROI needs at least 3 points!")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Allowed Directions")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Chọn các hướng đi được phép trong vùng này:"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        # Default: select primary direction
        if main._selected_direction == 'left':
            check_left.setChecked(True)
        elif main._selected_direction == 'straight':
            check_straight.setChecked(True)
        elif main._selected_direction == 'right':
            check_right.setChecked(True)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("\nHướng chính (Primary - for display):"))
        
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left")
        radio_straight = QRadioButton("⬆️ Straight")
        radio_right = QRadioButton("➡️ Right")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if main._selected_direction == 'left':
            radio_left.setChecked(True)
        elif main._selected_direction == 'straight':
            radio_straight.setChecked(True)
        elif main._selected_direction == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Get allowed directions
        allowed_dirs = []
        if check_left.isChecked():
            allowed_dirs.append('left')
        if check_straight.isChecked():
            allowed_dirs.append('straight')
        if check_right.isChecked():
            allowed_dirs.append('right')
        
        if not allowed_dirs:
            QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return
        
        # Get primary direction
        if radio_left.isChecked():
            primary_dir = 'left'
        elif radio_straight.isChecked():
            primary_dir = 'straight'
        elif radio_right.isChecked():
            primary_dir = 'right'
        else:
            primary_dir = allowed_dirs[0]
        
        # Create ROI
        roi_num = len(main.DIRECTION_ROIS) + 1
        new_roi = {
            'name': f'roi_{roi_num}',
            'points': main._tmp_direction_roi_pts.copy(),
            'allowed_directions': allowed_dirs,
            'primary_direction': primary_dir,
            'direction': primary_dir  # Backward compat
        }
        
        main.DIRECTION_ROIS.append(new_roi)
        
        allowed_str = '+'.join([d.upper() for d in allowed_dirs])
        print(f"✅ Created Direction ROI #{roi_num}: {allowed_str} (primary: {primary_dir.upper()}, {len(main._tmp_direction_roi_pts)} points)")
        self.status_label.setText(f"Status: Added ROI #{roi_num} - Allowed: {allowed_str}")
        
        # Reset
        main._drawing_mode = None
        main._tmp_direction_roi_pts = []
        self.btn_finish_direction_roi.setEnabled(False)
        
        # Update list
        self.update_direction_roi_list()
    
    def update_direction_roi_list(self):
        """Update direction ROI list widget"""
        main = self._get_globals()
        self.direction_roi_list.clear()
        for i, roi in enumerate(main.DIRECTION_ROIS):
            if 'allowed_directions' in roi:
                allowed = roi['allowed_directions']
                primary = roi.get('primary_direction', allowed[0])
                
                icons = []
                if 'left' in allowed:
                    icons.append('⬅️')
                if 'straight' in allowed:
                    icons.append('⬆️')
                if 'right' in allowed:
                    icons.append('➡️')
                
                icon_str = ''.join(icons)
                allowed_str = '+'.join([d[0].upper() for d in allowed])
                
                self.direction_roi_list.addItem(f"{icon_str} ROI {i+1}: {allowed_str} (primary: {primary[0].upper()}, {len(roi['points'])} pts)")
            else:
                direction = roi.get('direction', 'straight')
                direction_upper = direction.upper()
                color_mark = "🔴" if direction == 'left' else "🟢" if direction == 'straight' else "🟡"
                self.direction_roi_list.addItem(f"{color_mark} ROI {i+1}: {direction_upper} ({len(roi['points'])} pts)")
    
    def delete_direction_roi(self):
        """Delete direction ROI with selection dialog"""
        main = self._get_globals()
        
        if not main.DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No Direction ROIs to delete.")
            return
        
        # Show selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete Direction ROI")
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("<b>Select a Direction ROI to delete:</b>"))
        roi_list_widget = QListWidget()
        for i, roi in enumerate(main.DIRECTION_ROIS):
            direction = roi.get('primary_direction', roi.get('direction', 'unknown'))
            direction_upper = direction.upper()
            color_mark = "🔴" if direction == 'left' else "🟢" if direction == 'straight' else "🟡"
            roi_list_widget.addItem(f"{color_mark} ROI {i+1}: {direction_upper} ({len(roi['points'])} pts)")
        layout.addWidget(roi_list_widget)
        
        # Select first item by default
        if roi_list_widget.count() > 0:
            roi_list_widget.setCurrentRow(0)
        
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("Delete")
        btn_delete.setStyleSheet("background-color: #dc3545; color: white;")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(dialog.reject)
        
        def on_delete():
            sel_idx = roi_list_widget.currentRow()
            if sel_idx >= 0 and sel_idx < len(main.DIRECTION_ROIS):
                deleted_roi = main.DIRECTION_ROIS.pop(sel_idx)
                print(f"🗑️ Deleted Direction ROI: {deleted_roi['name']} ({deleted_roi.get('direction', 'unknown')})")
                self.status_label.setText(f"Status: Deleted ROI {sel_idx + 1}")
                self.update_direction_roi_list()
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a ROI to delete.")
        
        btn_delete.clicked.connect(on_delete)
        dialog.exec_()
    
    def start_edit_direction_roi(self):
        """Start editing direction ROI with selection dialog"""
        main = self._get_globals()
        
        if not main.DIRECTION_ROIS:
            QMessageBox.information(self, "No ROIs", "No Direction ROIs configured yet. Please add ROIs first.")
            return
        
        # Show selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Direction ROI to Edit")
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("<b>Select a Direction ROI to edit:</b>"))
        roi_list_widget = QListWidget()
        for i, roi in enumerate(main.DIRECTION_ROIS):
            direction = roi.get('primary_direction', roi.get('direction', 'unknown'))
            direction_upper = direction.upper()
            color_mark = "🔴" if direction == 'left' else "🟢" if direction == 'straight' else "🟡"
            roi_list_widget.addItem(f"{color_mark} ROI {i+1}: {direction_upper} ({len(roi['points'])} pts)")
        layout.addWidget(roi_list_widget)
        
        # Select first item by default
        if roi_list_widget.count() > 0:
            roi_list_widget.setCurrentRow(0)
        
        btn_layout = QHBoxLayout()
        btn_edit = QPushButton("Edit")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        btn_cancel.clicked.connect(dialog.reject)
        
        def on_edit():
            sel_idx = roi_list_widget.currentRow()
            if sel_idx >= 0:
                dialog.selected_idx = sel_idx
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a ROI to edit.")
        
        btn_edit.clicked.connect(on_edit)
        
        if dialog.exec_() == QDialog.Rejected:
            return
        
        selected_idx = getattr(dialog, 'selected_idx', -1)
        if selected_idx < 0:
            return
        
        self.roi_editor.start_editing(selected_idx, roi_type='direction')
        
        # Update UI
        self.btn_finish_edit_roi.setEnabled(True)
        self.btn_smooth_roi.setEnabled(True)
        self.btn_change_roi_direction.setEnabled(True)
        self.btn_edit_direction_roi.setEnabled(False)
        
        # Update menu actions
        self.action_finish_edit.setEnabled(True)
        self.action_smooth_roi.setEnabled(True)
        self.action_change_directions.setEnabled(True)
        
        # Disable other drawing buttons
        self.btn_add_direction_roi.setEnabled(False)
        self.btn_delete_direction_roi.setEnabled(False)
        
        roi = main.DIRECTION_ROIS[selected_idx]
        dir_display = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
        self.status_label.setText(f"Status: Editing {dir_display} ROI - {len(roi['points'])} points | "
                                 "Left-click+drag=move | Double-click=add | Right-click=delete")
        
        print(f"✏️ Editing Direction ROI {selected_idx}: {dir_display} ({len(roi['points'])} points)")
    
    def finish_edit_roi(self):
        """Finish editing current ROI and show direction selection dialog"""
        main = self._get_globals()
        
        print(f"🔍 finish_edit_roi called: is_editing={self.roi_editor.is_editing()}, "
              f"is_editing_direction={self.roi_editor.is_editing_direction()}, "
              f"editing_type={self.roi_editor.editing_type}")
        
        # Only proceed if editing a direction ROI
        if not self.roi_editor.is_editing_direction():
            print("⚠️ finish_edit_roi: NOT editing direction ROI, returning")
            return
        
        roi_idx = self.roi_editor.editing_roi_index
        if roi_idx < 0 or roi_idx >= len(main.DIRECTION_ROIS):
            print(f"⚠️ finish_edit_roi: Invalid roi_idx={roi_idx}")
            return
            
        roi = main.DIRECTION_ROIS[roi_idx]
        
        self.roi_editor.finish_editing()
        
        # Update UI
        self.btn_finish_edit_roi.setEnabled(False)
        self.btn_smooth_roi.setEnabled(False)
        self.btn_change_roi_direction.setEnabled(True)
        self.btn_edit_direction_roi.setEnabled(True)
        self.btn_add_direction_roi.setEnabled(True)
        self.btn_delete_direction_roi.setEnabled(True)
        
        # Update menu actions
        self.action_finish_edit.setEnabled(False)
        self.action_smooth_roi.setEnabled(False)
        self.action_change_directions.setEnabled(True)
        
        # Show direction selection dialog
        self._show_direction_selection_dialog(roi_idx)
        
        dir_display = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
        self.status_label.setText(f"Status: Finished editing {dir_display} ROI - {len(roi['points'])} points")
        print(f"✅ Finished editing ROI {roi_idx}: {len(roi['points'])} points")
        
        self.update_direction_roi_list()
    
    def _show_direction_selection_dialog(self, roi_idx):
        """Show dialog to select allowed directions for a ROI"""
        main = self._get_globals()
        
        if roi_idx < 0 or roi_idx >= len(main.DIRECTION_ROIS):
            return
            
        roi = main.DIRECTION_ROIS[roi_idx]
        
        current_allowed = roi.get('allowed_directions', [roi.get('direction', 'straight')])
        current_primary = roi.get('primary_direction', roi.get('direction', 'straight'))
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Allowed Directions - ROI {roi_idx + 1}")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(f"<b>ROI #{roi_idx + 1}</b><br>Chọn các hướng đi được phép trong vùng này:"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        check_left.setChecked('left' in current_allowed)
        check_straight.setChecked('straight' in current_allowed)
        check_right.setChecked('right' in current_allowed)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("<br><b>Hướng chính</b> (Primary - for display):"))
        
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left")
        radio_straight = QRadioButton("⬆️ Straight")
        radio_right = QRadioButton("➡️ Right")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if current_primary == 'left':
            radio_left.setChecked(True)
        elif current_primary == 'straight':
            radio_straight.setChecked(True)
        elif current_primary == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        new_allowed = []
        if check_left.isChecked():
            new_allowed.append('left')
        if check_straight.isChecked():
            new_allowed.append('straight')
        if check_right.isChecked():
            new_allowed.append('right')
        
        if not new_allowed:
            QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return
        
        if radio_left.isChecked():
            new_primary = 'left'
        elif radio_straight.isChecked():
            new_primary = 'straight'
        elif radio_right.isChecked():
            new_primary = 'right'
        else:
            new_primary = new_allowed[0]
        
        roi['allowed_directions'] = new_allowed
        roi['primary_direction'] = new_primary
        roi['direction'] = new_primary
        
        allowed_str = '+'.join([d.upper() for d in new_allowed])
        print(f"🔄 Updated ROI {roi_idx + 1} directions: {allowed_str} (primary: {new_primary.upper()})")
    
    def smooth_current_roi(self):
        """Smooth the currently editing ROI"""
        main = self._get_globals()
        
        if not self.roi_editor.is_editing():
            return
        
        roi_idx = self.roi_editor.editing_roi_index
        roi = main.DIRECTION_ROIS[roi_idx]
        
        old_count = len(roi['points'])
        
        epsilon, ok = QInputDialog.getDouble(
            self,
            "Smooth ROI",
            "Epsilon factor (0.005-0.05):\nLower = more detail, Higher = fewer points",
            0.01, 0.001, 0.1, 3
        )
        
        if not ok:
            return
        
        roi['points'] = self.roi_editor.smooth_roi(roi['points'], epsilon_factor=epsilon)
        
        new_count = len(roi['points'])
        self.status_label.setText(f"Status: Smoothed ROI - {old_count} → {new_count} points")
        print(f"🔧 Smoothed ROI: {old_count} → {new_count} points (epsilon={epsilon})")
        
        self.update_direction_roi_list()
    
    def change_roi_directions(self):
        """Change allowed directions for a ROI (can be called anytime)"""
        main = self._get_globals()
        
        # If editing, use current editing index
        if self.roi_editor.is_editing():
            roi_idx = self.roi_editor.editing_roi_index
        else:
            # Otherwise, show selection dialog
            if not main.DIRECTION_ROIS:
                QMessageBox.information(self, "No ROIs", "No Direction ROIs configured yet.")
                return
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Direction ROI")
            dialog.setMinimumSize(400, 300)
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel("<b>Select a ROI to change directions:</b>"))
            roi_list_widget = QListWidget()
            for i, roi in enumerate(main.DIRECTION_ROIS):
                direction = roi.get('primary_direction', roi.get('direction', 'unknown'))
                direction_upper = direction.upper()
                color_mark = "🔴" if direction == 'left' else "🟢" if direction == 'straight' else "🟡"
                roi_list_widget.addItem(f"{color_mark} ROI {i+1}: {direction_upper} ({len(roi['points'])} pts)")
            layout.addWidget(roi_list_widget)
            
            if roi_list_widget.count() > 0:
                roi_list_widget.setCurrentRow(0)
            
            btn_layout = QHBoxLayout()
            btn_select = QPushButton("Select")
            btn_cancel = QPushButton("Cancel")
            btn_layout.addWidget(btn_select)
            btn_layout.addWidget(btn_cancel)
            layout.addLayout(btn_layout)
            
            btn_cancel.clicked.connect(dialog.reject)
            
            def on_select():
                sel_idx = roi_list_widget.currentRow()
                if sel_idx >= 0:
                    dialog.selected_idx = sel_idx
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "No Selection", "Please select a ROI.")
            
            btn_select.clicked.connect(on_select)
            
            if dialog.exec_() == QDialog.Rejected:
                return
            
            roi_idx = getattr(dialog, 'selected_idx', -1)
            if roi_idx < 0:
                return
        
        roi = main.DIRECTION_ROIS[roi_idx]
        
        current_allowed = roi.get('allowed_directions', [roi.get('direction', 'straight')])
        current_primary = roi.get('primary_direction', roi.get('direction', 'straight'))
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Change ROI {roi_idx + 1} Directions")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(f"<b>ROI #{roi_idx + 1}</b><br>Chọn các hướng đi được phép:"))
        
        check_left = QCheckBox("⬅️ Rẽ trái (Left Turn)")
        check_straight = QCheckBox("⬆️ Đi thẳng (Straight)")
        check_right = QCheckBox("➡️ Rẽ phải (Right Turn)")
        
        check_left.setChecked('left' in current_allowed)
        check_straight.setChecked('straight' in current_allowed)
        check_right.setChecked('right' in current_allowed)
        
        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)
        
        layout.addWidget(QLabel("<br><b>Hướng chính</b> (Primary - for display color):"))
        
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("⬅️ Left (Red 🔴)")
        radio_straight = QRadioButton("⬆️ Straight (Green 🟢)")
        radio_right = QRadioButton("➡️ Right (Yellow 🟡)")
        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)
        
        if current_primary == 'left':
            radio_left.setChecked(True)
        elif current_primary == 'straight':
            radio_straight.setChecked(True)
        elif current_primary == 'right':
            radio_right.setChecked(True)
        
        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        new_allowed = []
        if check_left.isChecked():
            new_allowed.append('left')
        if check_straight.isChecked():
            new_allowed.append('straight')
        if check_right.isChecked():
            new_allowed.append('right')
        
        if not new_allowed:
            QMessageBox.warning(self, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return
        
        if radio_left.isChecked():
            new_primary = 'left'
        elif radio_straight.isChecked():
            new_primary = 'straight'
        elif radio_right.isChecked():
            new_primary = 'right'
        else:
            new_primary = new_allowed[0]
        
        roi['allowed_directions'] = new_allowed
        roi['primary_direction'] = new_primary
        roi['direction'] = new_primary
        
        allowed_str = '+'.join([d.upper() for d in new_allowed])
        print(f"🔄 Changed ROI {roi_idx + 1} directions: {allowed_str} (primary: {new_primary.upper()})")
        self.status_label.setText(f"Status: ROI {roi_idx + 1} - Allowed: {allowed_str}")
        
        self.update_direction_roi_list()
    
    def save_direction_rois(self):
        """Save direction ROIs to JSON file"""
        main = self._get_globals()
        
        if not main.DIRECTION_ROIS:
            QMessageBox.warning(self, "No ROIs", "No Direction ROIs to save!")
            return
        
        video_name = Path(self.video_path).stem
        default_name = f"{video_name}_direction_rois.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Direction ROIs", default_name,
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            data = {
                'video': Path(self.video_path).name,
                'frame_shape': list(self.current_frame.shape[:2]) if self.current_frame is not None else [0, 0],
                'rois': list(main.DIRECTION_ROIS)
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Saved {len(main.DIRECTION_ROIS)} Direction ROIs to: {file_path}")
            self.status_label.setText(f"Status: Saved {len(main.DIRECTION_ROIS)} ROIs to JSON")
            QMessageBox.information(self, "Saved", f"Saved {len(main.DIRECTION_ROIS)} Direction ROIs successfully!")
    
    def load_direction_rois(self):
        """Load direction ROIs from JSON file"""
        main = self._get_globals()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Direction ROIs", "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Clear and extend instead of reassigning reference
                main.DIRECTION_ROIS.clear()
                main.DIRECTION_ROIS.extend(data.get('rois', []))
                
                print(f"📂 Loaded {len(main.DIRECTION_ROIS)} Direction ROIs from: {file_path}")
                self.status_label.setText(f"Status: Loaded {len(main.DIRECTION_ROIS)} ROIs")
                self.update_direction_roi_list()
                
                QMessageBox.information(self, "Loaded", f"Loaded {len(main.DIRECTION_ROIS)} Direction ROIs successfully!")
                
            except Exception as e:
                print(f"❌ Error loading ROIs: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load ROIs: {e}")
    
    def toggle_direction_rois(self):
        """Toggle showing direction ROIs on video"""
        from PyQt5.QtWidgets import QAction
        sender = self.sender()
        if isinstance(sender, QAction):
            self.show_direction_rois = sender.isChecked()
            if hasattr(self, 'btn_toggle_direction_rois'):
                self.btn_toggle_direction_rois.setChecked(self.show_direction_rois)
        else:
            self.show_direction_rois = self.btn_toggle_direction_rois.isChecked()
            if hasattr(self, 'action_toggle_rois'):
                self.action_toggle_rois.setChecked(self.show_direction_rois)
        
        if self.show_direction_rois:
            if hasattr(self, 'btn_toggle_direction_rois'):
                self.btn_toggle_direction_rois.setText("Show Direction ROIs: ON")
            print("👁️ Direction ROIs visible")
        else:
            if hasattr(self, 'btn_toggle_direction_rois'):
                self.btn_toggle_direction_rois.setText("Show Direction ROIs: OFF")
            print("🙈 Direction ROIs hidden")
    
    def update_direction_roi_list(self):
        """Update direction ROI list widget"""
        main = self._get_globals()
        
        if not hasattr(self, 'direction_roi_list'):
            return
        
        self.direction_roi_list.clear()
        for idx, roi in enumerate(main.DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            secondary_dirs = roi.get('secondary_directions', [])
            allowed_dirs = [primary_dir] + [d.upper() for d in secondary_dirs]
            points = roi.get('points', [])
            self.direction_roi_list.addItem(f"ROI {idx}: {', '.join(allowed_dirs)} - {len(points)} points")

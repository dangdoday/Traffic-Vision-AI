"""
Dialog Handler Mixin
Contains methods for showing various dialogs (about, shortcuts, settings, lists)
"""
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton


class DialogHandlerMixin:
    """Mixin class for dialog handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from integrated_main - lazy import"""
        import integrated_main
        return integrated_main
    
    def show_about(self):
        '''Show about dialog'''
        QMessageBox.about(
            self,
            "About Traffic Violation Detector",
            "<h2>Traffic Violation Detection System</h2>"
            "<p>Version 2.0</p>"
            "<p>Advanced traffic violation detection using YOLOv8</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Lane violation detection</li>"
            "<li>Stopline crossing detection</li>"
            "<li>Traffic light violation (direction-aware)</li>"
            "<li>Multi-direction ROI support</li>"
            "<li>Reference vector for tilted cameras</li>"
            "<li>Auto save/load configuration</li>"
            "</ul>"
        )
    
    def show_shortcuts(self):
        '''Show keyboard shortcuts help'''
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "<h3>Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>Ctrl+O</b></td><td>Open Video</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save Configuration</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Load Configuration</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Exit</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>L</b></td><td>Add Lane</td></tr>"
            "<tr><td><b>S</b></td><td>Set Stop Line</td></tr>"
            "<tr><td><b>T</b></td><td>Add Traffic Light</td></tr>"
            "<tr><td><b>D</b></td><td>Draw Direction ROI</td></tr>"
            "<tr><td><b>R</b></td><td>Set Reference Vector</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Enter</b></td><td>Finish Drawing (Lane/ROI/Ref Vector)</td></tr>"
            "<tr><td><b>E</b></td><td>Edit Direction ROI</td></tr>"
            "<tr><td><b>Return</b></td><td>Finish Editing</td></tr>"
            "<tr><td><b>Delete</b></td><td>Delete Selected</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Space</b></td><td>Start/Stop Detection</td></tr>"
            "<tr><td><b>F1</b></td><td>Show This Help</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Right-Click</b></td><td>Context Menu on Video</td></tr>"
            "</table>"
        )
    
    def show_imgsz_dialog(self):
        """Show dialog to set image size"""
        from PyQt5.QtWidgets import QInputDialog
        current_imgsz = self.imgsz_spinbox.value()
        imgsz, ok = QInputDialog.getInt(
            self,
            "Set Image Size",
            "Enter image size (320-1280, multiple of 32):",
            current_imgsz,
            320,
            1280,
            32
        )
        if ok:
            self.imgsz_spinbox.setValue(imgsz)
            self.on_imgsz_changed(imgsz)
            self.statusBar().showMessage(f"Image size set to: {imgsz}")
    
    def show_conf_dialog(self):
        """Show dialog to set confidence threshold"""
        from PyQt5.QtWidgets import QInputDialog
        current_conf = self.conf_spinbox.value()
        conf, ok = QInputDialog.getDouble(
            self,
            "Set Confidence Threshold",
            "Enter confidence threshold (0.1-0.95):",
            current_conf,
            0.1,
            0.95,
            2
        )
        if ok:
            self.conf_spinbox.setValue(conf)
            self.on_conf_changed(conf)
            self.statusBar().showMessage(f"Confidence threshold set to: {conf:.2f}")
    
    def show_lane_list_dialog(self):
        """Show dialog with lane list"""
        main = self._get_globals()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Lane List")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout()
        
        lane_list = QListWidget()
        for idx, lane in enumerate(main.LANE_CONFIGS, start=1):
            allowed = lane.get('allowed_labels', ['all'])
            lane_list.addItem(f"Lane {idx}: {len(lane['poly'])} points - {', '.join(allowed)}")
        
        layout.addWidget(QLabel("<b>Configured Lanes:</b>"))
        layout.addWidget(lane_list)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def show_direction_list_dialog(self):
        """Show dialog with direction ROI list"""
        main = self._get_globals()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Direction ROI List")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        direction_list = QListWidget()
        for idx, roi in enumerate(main.DIRECTION_ROIS, start=1):
            primary_dir = roi.get('primary_direction', roi.get('direction', 'unknown')).upper()
            secondary_dirs = roi.get('secondary_directions', [])
            allowed_dirs = [primary_dir] + [d.upper() for d in secondary_dirs]
            
            # Get traffic light info
            tl_colors = []
            for tl_idx in roi.get('tl_ids', []):
                if tl_idx < len(main.TL_ROIS):
                    color = main.TL_ROIS[tl_idx].get('last_color', 'unknown')
                    tl_colors.append(f"TL{tl_idx + 1}:{color}")
            
            tl_info = ' | '.join(tl_colors) if tl_colors else 'No TL'
            points = roi.get('points', [])
            direction_list.addItem(
                f"ROI {idx}: {', '.join(allowed_dirs)} - {len(points)} pts - {tl_info}"
            )
        
        layout.addWidget(QLabel("<b>Configured Direction ROIs:</b>"))
        layout.addWidget(direction_list)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.setLayout(layout)
        dialog.exec_()

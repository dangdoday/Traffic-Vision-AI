"""
Configuration Handler Mixin
Contains methods for saving and loading configurations
"""
import math
from PyQt5.QtWidgets import QMessageBox


class ConfigHandlerMixin:
    """Mixin class for configuration handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from integrated_main - lazy import"""
        import integrated_main
        return integrated_main
    
    def save_configuration(self):
        """Save all ROI configurations to file"""
        main = self._get_globals()
        
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first before saving configuration.")
            return
        
        # Convert reference vector to tuple format if set
        ref_vector = None
        if self.ref_vector_p1 and self.ref_vector_p2:
            ref_vector = (tuple(self.ref_vector_p1), tuple(self.ref_vector_p2))
        
        # Save using ConfigManager
        success = self.config_manager.save_config(
            video_path=self.video_path,
            lane_configs=main.LANE_CONFIGS,
            stop_line=main.STOP_LINE,
            tl_rois=main.TL_ROIS,
            direction_rois=main.DIRECTION_ROIS,
            reference_vector=ref_vector
        )
        
        if success:
            config_path = self.config_manager.get_config_path(self.video_path)
            QMessageBox.information(
                self, 
                "Configuration Saved", 
                f"✅ All ROIs saved successfully!\n\nFile: {config_path.name}\n\n"
                f"- Lanes: {len(main.LANE_CONFIGS)}\n"
                f"- Stopline: {'Yes' if main.STOP_LINE else 'No'}\n"
                f"- Traffic Lights: {len(main.TL_ROIS)}\n"
                f"- Direction Zones: {len(main.DIRECTION_ROIS)}\n"
                f"- Reference Vector: {'Yes' if ref_vector else 'No'}"
            )
            self.config_status_label.setText(f"✅ Config: Saved to file")
            self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
        else:
            QMessageBox.critical(self, "Save Failed", "❌ Failed to save configuration. Check console for errors.")
    
    def load_configuration(self):
        """Manually load configuration from file"""
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first before loading configuration.")
            return
        
        result = self.config_manager.load_config(self.video_path)
        
        if result is None:
            QMessageBox.warning(
                self, 
                "No Configuration", 
                "No saved configuration found for this video.\n\n"
                "Draw ROIs manually and save them for future use."
            )
            return
        
        self._apply_loaded_config(result)
        
        config_path = self.config_manager.get_config_path(self.video_path)
        QMessageBox.information(
            self, 
            "Configuration Loaded", 
            f"✅ Configuration loaded successfully!\n\nFile: {config_path.name}\n\n"
            f"- Lanes: {len(result['lanes'])}\n"
            f"- Stopline: {'Yes' if result['stopline'] else 'No'}\n"
            f"- Traffic Lights: {len(result['traffic_lights'])}\n"
            f"- Direction Zones: {len(result['direction_zones'])}\n"
            f"- Reference Vector: {'Yes' if result['reference_vector'] else 'No'}"
        )
        
        self.config_status_label.setText(f"✅ Config: Loaded from file")
        self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
    
    def auto_load_configuration(self):
        """Auto-load configuration without showing message box"""
        result = self.config_manager.load_config(self.video_path)
        
        if result is None:
            return False
        
        self._apply_loaded_config(result)
        return True
    
    def _apply_loaded_config(self, config):
        """Apply loaded configuration to global variables and UI"""
        main = self._get_globals()
        
        # Load lanes
        main.LANE_CONFIGS.clear()
        for lane_data in config['lanes']:
            main.LANE_CONFIGS.append({
                'poly': lane_data['points'],
                'points': lane_data['points'],
                'label': lane_data.get('label', 'Unnamed Lane'),
                'allowed_types': lane_data.get('allowed_types', [])
            })
        
        # Update lane list widget
        self.lane_list.clear()
        for lane in main.LANE_CONFIGS:
            self.lane_list.addItem(lane.get('label', 'Unnamed Lane'))
        
        # Load stopline
        main.STOP_LINE = config['stopline']
        
        # Load traffic lights
        main.TL_ROIS.clear()
        main.TL_ROIS.extend(config['traffic_lights'])
        
        # Load direction zones
        main.DIRECTION_ROIS.clear()
        main.DIRECTION_ROIS.extend(config['direction_zones'])
        
        # Update direction ROI list widget
        self.update_direction_roi_list()
        
        # Load reference vector
        if config['reference_vector']:
            self.ref_vector_p1 = list(config['reference_vector'][0])
            self.ref_vector_p2 = list(config['reference_vector'][1])
            dx = self.ref_vector_p2[0] - self.ref_vector_p1[0]
            dy = self.ref_vector_p2[1] - self.ref_vector_p1[1]
            angle = math.degrees(math.atan2(dy, dx))
            self.ref_vector_label.setText(f"✅ Ref Vector: {angle:.1f}° ({dx:.0f}, {dy:.0f})")
            self.ref_vector_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            print(f"✅ Reference Vector loaded: {angle:.1f}° from {self.ref_vector_p1} to {self.ref_vector_p2}")
            
            # ⚠️ CRITICAL: Apply reference angle to VehicleTracker
            if hasattr(self, 'thread') and self.thread is not None:
                self.thread.set_reference_angle(angle)
                print(f"🎯 Applied ref_angle={angle:.1f}° to VehicleTracker from config")
        else:
            self.ref_vector_p1 = None
            self.ref_vector_p2 = None
            self.ref_vector_label.setText("⚠️ Ref Vector: Not set - Set it for better accuracy!")
            self.ref_vector_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            if main.DIRECTION_ROIS:  # Warn if direction ROIs exist but no ref vector
                print("⚠️ WARNING: Direction ROIs loaded but Reference Vector NOT SET!")
                print("   → This may affect turn detection accuracy")
                print("   → Recommend: Set Reference Vector before starting detection")
        
        print(f"✅ Configuration applied to UI and global variables")

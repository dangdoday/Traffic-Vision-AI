"""
Configuration Handler Mixin
Contains methods for saving and loading configurations
"""
import math
import sys
from PyQt5.QtWidgets import QMessageBox


class ConfigHandlerMixin:
    """Mixin class for configuration handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        # When integrated_main.py is run directly, it's loaded as __main__
        # When imported by handlers, we need to get __main__ to access the same globals
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            # Verify this is the correct module by checking for expected attributes
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        # Fallback to importing integrated_main (shouldn't happen in normal use)
        import integrated_main
        return integrated_main
    
    def save_configuration(self):
        """Save all ROI configurations to file"""
        main = self._get_globals()
        
        # Debug: Print what we're trying to save
        print(f"🔍 [save_configuration] TL_ROIS id={id(main.TL_ROIS)}, len={len(main.TL_ROIS)}")
        print(f"🔍 [save_configuration] DIRECTION_ROIS len={len(main.DIRECTION_ROIS)}")
        print(f"🔍 [save_configuration] LANE_CONFIGS len={len(main.LANE_CONFIGS)}")
        print(f"🔍 [save_configuration] STOP_LINE = {main.STOP_LINE}")
        
        if not self.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first before saving configuration.")
            return
        
        # Convert reference vector to tuple format if set
        ref_vector = None
        if self.ref_vector_p1 and self.ref_vector_p2:
            ref_vector = (tuple(self.ref_vector_p1), tuple(self.ref_vector_p2))
        
        # Get current model info
        model_type = self.current_model_type if hasattr(self, 'current_model_type') else None
        weight_name = self.weight_combo.currentText() if hasattr(self, 'weight_combo') else None
        imgsz = self.imgsz_spinbox.value() if hasattr(self, 'imgsz_spinbox') else None
        conf_threshold = self.conf_spinbox.value() if hasattr(self, 'conf_spinbox') else None
        
        # Save using ConfigManager
        success = self.config_manager.save_config(
            video_path=self.video_path,
            lane_configs=main.LANE_CONFIGS,
            stop_line=main.STOP_LINE,
            tl_rois=main.TL_ROIS,
            direction_rois=main.DIRECTION_ROIS,
            reference_vector=ref_vector,
            model_type=model_type,
            weight_name=weight_name,
            imgsz=imgsz,
            conf_threshold=conf_threshold
        )
        
        if success:
            config_path = self.config_manager.get_config_path(self.video_path)
            
            # Build message with model info
            message_parts = [
                f"✅ All ROIs saved successfully!\n\nFile: {config_path.name}\n",
                f"- Lanes: {len(main.LANE_CONFIGS)}",
                f"- Stopline: {'Yes' if main.STOP_LINE else 'No'}",
                f"- Traffic Lights: {len(main.TL_ROIS)}",
                f"- Direction Zones: {len(main.DIRECTION_ROIS)}",
                f"- Reference Vector: {'Yes' if ref_vector else 'No'}"
            ]
            
            # Add model info if available
            if model_type and weight_name:
                message_parts.append(f"- Model: {model_type} ({weight_name})")
                if imgsz:
                    message_parts.append(f"  ImgSize: {imgsz}")
                if conf_threshold:
                    message_parts.append(f"  Confidence: {conf_threshold}")
            
            QMessageBox.information(
                self, 
                "Configuration Saved", 
                "\n".join(message_parts)
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
        
        # Get config path first
        config_path = self.config_manager.get_config_path(self.video_path)
        
        # Build message with model info if available
        message_parts = [
            f"✅ Configuration loaded successfully!\n\nFile: {config_path.name}\n",
            f"- Lanes: {len(result['lanes'])}",
            f"- Stopline: {'Yes' if result['stopline'] else 'No'}",
            f"- Traffic Lights: {len(result['traffic_lights'])}",
            f"- Direction Zones: {len(result['direction_zones'])}",
            f"- Reference Vector: {'Yes' if result['reference_vector'] else 'No'}"
        ]
        
        # Add model info if available
        model_info = result.get('model', {})
        if model_info and model_info.get('type'):
            message_parts.append(f"- Model: {model_info['type']} ({model_info.get('weight', 'N/A')})")
            if model_info.get('imgsz'):
                message_parts.append(f"  ImgSize: {model_info['imgsz']}")
            if model_info.get('conf_threshold'):
                message_parts.append(f"  Confidence: {model_info['conf_threshold']}")
        
        QMessageBox.information(
            self, 
            "Configuration Loaded", 
            "\n".join(message_parts)
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
            # Support both 'allowed_types' and 'allowed_labels' keys
            allowed = lane_data.get('allowed_types', lane_data.get('allowed_labels', []))
            main.LANE_CONFIGS.append({
                'poly': lane_data['points'],
                'points': lane_data['points'],
                'label': lane_data.get('label', 'Unnamed Lane'),
                'allowed_types': allowed,
                'allowed_labels': allowed  # Also set allowed_labels for compatibility
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
        print(f"🚦 [config_handler] Loaded TL_ROIS: count={len(main.TL_ROIS)}, id={id(main.TL_ROIS)}")
        for i, roi in enumerate(main.TL_ROIS):
            print(f"   TL {i}: type={roi[4]}, color={roi[5]}")
        
        # ⚠️ CRITICAL: Enable TL tracking and update colors from current frame
        if len(main.TL_ROIS) > 0:
            self.tl_tracking_active = True
            print(f"✅ Loaded {len(main.TL_ROIS)} traffic lights, tracking enabled")
            
            # Update colors immediately if we have a current frame
            if self.current_frame is not None:
                # Force immediate update by resetting frame counter
                self.tl_force_update_on_next_frame = True
                self.update_tl_colors(self.current_frame)
                print("🎨 Traffic light colors updated from current frame")
            else:
                # Set flag to force update on first frame
                self.tl_force_update_on_next_frame = True
                print("⚠️ No current frame available, will force update colors on next frame")
        else:
            self.tl_tracking_active = False
            print("ℹ️ No traffic lights in config")
        
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
        
        # Load model configuration if available
        model_config = config.get('model', {})
        print(f"🔍 Model config from file: {model_config}")
        
        if model_config and model_config.get('type') and model_config.get('weight'):
            model_type = model_config['type']
            weight_name = model_config['weight']
            imgsz = model_config.get('imgsz')
            conf_threshold = model_config.get('conf_threshold')
            
            print(f"🔄 Loading model from config: {model_type} - {weight_name} (imgsz={imgsz}, conf={conf_threshold})")
            
            # Check if model exists in available models
            if model_type in self.available_models:
                # Temporarily block signals to prevent auto-loading
                self.model_type_combo.blockSignals(True)
                self.weight_combo.blockSignals(True)
                
                # Update model type combo box
                model_types = list(self.available_models.keys())
                if model_type in model_types:
                    model_idx = model_types.index(model_type)
                    self.model_type_combo.setCurrentIndex(model_idx)
                    print(f"  ↳ Set model type combo to index {model_idx} ({model_type})")
                
                # Update weight combo box
                self.update_weight_combo()
                weights = self.available_models[model_type]["weights"]
                if weight_name in weights:
                    weight_idx = weights.index(weight_name)
                    self.weight_combo.setCurrentIndex(weight_idx)
                    print(f"  ↳ Set weight combo to index {weight_idx} ({weight_name})")
                
                # Re-enable signals
                self.model_type_combo.blockSignals(False)
                self.weight_combo.blockSignals(False)
                
                # Load the model
                success = self.load_model(model_type, weight_name)
                
                if success:
                    # Apply saved parameters
                    if imgsz is not None and hasattr(self, 'imgsz_spinbox'):
                        self.imgsz_spinbox.setValue(imgsz)
                        if self.current_model_config:
                            self.current_model_config['default_imgsz'] = imgsz
                    
                    if conf_threshold is not None and hasattr(self, 'conf_spinbox'):
                        self.conf_spinbox.setValue(conf_threshold)
                        if self.current_model_config:
                            self.current_model_config['default_conf'] = conf_threshold
                    
                    # Update thread config (check model_config is not None)
                    if hasattr(self, 'thread') and self.thread is not None and self.thread.model_config is not None:
                        if imgsz is not None:
                            self.thread.model_config['default_imgsz'] = imgsz
                        if conf_threshold is not None:
                            self.thread.model_config['default_conf'] = conf_threshold
                    
                    self.update_model_info_label()
                    print(f"✅ Model loaded from config: {model_type} - {weight_name} (imgsz={imgsz}, conf={conf_threshold})")
                else:
                    print(f"⚠️ Failed to load model from config: {model_type} - {weight_name}")
            else:
                print(f"⚠️ Model type '{model_type}' not found in available models")
        
        print(f"✅ Configuration applied to UI and global variables")

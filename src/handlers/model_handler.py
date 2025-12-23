"""
Model Handler Mixin
Contains methods for YOLO model loading and configuration management
"""
from PyQt5.QtWidgets import QMessageBox


class ModelHandlerMixin:
    """Mixin class for model loading and configuration in MainWindow"""
    
    def _get_globals(self):
        """Get globals from integrated_main - lazy import"""
        import integrated_main
        return integrated_main
    
    def load_model_from_menu(self, model_type):
        """Load model when selected from menu"""
        if model_type in self.available_models:
            first_weight = self.available_models[model_type]["weights"][0]
            self.load_model(model_type, first_weight)
            self.statusBar().showMessage(f"Loaded model: {model_type}")
    
    def load_model(self, model_type, weight_name):
        """Load model dynamically based on selection"""
        main = self._get_globals()
        
        if not main.YOLO_AVAILABLE:
            print("⚠️ YOLO not available")
            return False
        
        try:
            from model_config import get_weight_path, get_model_config
            from ultralytics import YOLO
            
            print(f"🔄 Loading {model_type} model: {weight_name}...")
            weight_path = get_weight_path(model_type, weight_name)
            self.yolo_model = YOLO(weight_path)
            self.current_model_type = model_type
            self.current_model_config = get_model_config(model_type)
            
            # Update thread model if thread exists and was already initialized
            if hasattr(self, 'thread') and hasattr(self.thread, 'model_loaded'):
                if self.thread.model_loaded:
                    self.thread.set_model(self.yolo_model)
                    self.thread.model_config = self.current_model_config
            
            # Update spinboxes with model's default values
            if hasattr(self, 'imgsz_spinbox'):
                self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
            if hasattr(self, 'conf_spinbox'):
                self.conf_spinbox.setValue(self.current_model_config['default_conf'])
            
            print(f"✅ Model loaded: {weight_path}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Status: Loaded {model_type} - {weight_name}")
            return True
        except Exception as e:
            import traceback
            print(f"❌ Failed to load model: {e}")
            print(traceback.format_exc())
            if hasattr(self, 'status_label'):
                QMessageBox.warning(self, "Model Load Error", f"Could not load model:\n{e}")
            return False
    
    def update_weight_combo(self):
        """Update weight dropdown based on selected model type"""
        self.weight_combo.clear()
        
        if not self.available_models:
            return
        
        # Get current model type from combo
        current_idx = self.model_type_combo.currentIndex()
        if current_idx < 0:
            return
        
        model_type = list(self.available_models.keys())[current_idx]
        weights = self.available_models[model_type]["weights"]
        
        for weight in weights:
            self.weight_combo.addItem(weight)
    
    def update_model_info_label(self):
        """Update model info label with current config"""
        if self.current_model_config:
            # Get values from spinboxes if they exist
            imgsz = self.imgsz_spinbox.value() if hasattr(self, 'imgsz_spinbox') else self.current_model_config['default_imgsz']
            conf = self.conf_spinbox.value() if hasattr(self, 'conf_spinbox') else self.current_model_config['default_conf']
            info = f"Using: ImgSize={imgsz} | Conf={conf}"
            self.model_info_label.setText(info)
        else:
            self.model_info_label.setText("No model loaded")
    
    def on_model_type_changed(self):
        """Handle model type selection change"""
        self.update_weight_combo()
        
        # Auto-load first weight of new model type
        if self.weight_combo.count() > 0:
            self.on_weight_changed()
    
    def on_weight_changed(self):
        """Handle weight selection change"""
        if self.weight_combo.currentIndex() < 0:
            return
        
        current_idx = self.model_type_combo.currentIndex()
        if current_idx < 0:
            return
        
        model_type = list(self.available_models.keys())[current_idx]
        weight_name = self.weight_combo.currentText()
        
        if weight_name:
            success = self.load_model(model_type, weight_name)
            if success:
                # Update spinboxes with model default values
                if self.current_model_config:
                    self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
                    self.conf_spinbox.setValue(self.current_model_config['default_conf'])
                self.update_model_info_label()
    
    def on_imgsz_changed(self):
        """Handle image size change"""
        new_imgsz = self.imgsz_spinbox.value()
        print(f"📐 ImgSize changed to: {new_imgsz}")
        
        # Update current config
        if self.current_model_config:
            self.current_model_config['default_imgsz'] = new_imgsz
        
        # Update thread config if running
        if hasattr(self, 'thread') and self.thread.model_config:
            self.thread.model_config['default_imgsz'] = new_imgsz
            print(f"✅ Thread ImgSize updated to: {new_imgsz}")
        
        self.update_model_info_label()
    
    def on_conf_changed(self):
        """Handle confidence threshold change"""
        new_conf = round(self.conf_spinbox.value(), 2)  # Round to 2 decimals
        print(f"🎯 Confidence changed to: {new_conf}")
        
        # Update current config
        if self.current_model_config:
            self.current_model_config['default_conf'] = new_conf
        
        # Update thread config if running
        if hasattr(self, 'thread') and self.thread.model_config:
            self.thread.model_config['default_conf'] = new_conf
            print(f"✅ Thread Confidence updated to: {new_conf}")
        
        self.update_model_info_label()

"""
Model Handler Mixin
Contains methods for YOLO model loading and configuration management
"""
import sys
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt
import torch


class ModelHandlerMixin:
    """Mixin class for model loading and configuration in MainWindow"""
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        import integrated_main
        return integrated_main
    
    def load_model_from_menu(self, model_type):
        """Load model when selected from menu"""
        if model_type in self.available_models:
            first_weight = self.available_models[model_type]["weights"][0]
            self.load_model(model_type, first_weight)
            self.statusBar().showMessage(f"Loaded model: {model_type}")
    
    def load_model(self, model_type, weight_name, async_mode=False):
        """Load model with optional async mode
        
        Args:
            model_type: Type of model
            weight_name: Weight file name
            async_mode: If True, load in background (with progress dialog). 
                       If False, load synchronously (for startup).
        """
        main = self._get_globals()
        
        if not main.YOLO_AVAILABLE:
            print("⚠️ YOLO not available")
            return False
        
        try:
            from model_config import get_weight_path, get_model_config
            from ultralytics import YOLO
            from core.model_loader import ModelLoaderThread
            
            weight_path = get_weight_path(model_type, weight_name)
            device = getattr(self, 'device', 'cuda:0' if torch.cuda.is_available() else 'cpu')
            
            if async_mode:
                # Load asynchronously with progress dialog (for menu selection)
                print(f"🔄 Loading {model_type} model (async): {weight_name}...")
                self.model_loading = True
                
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"Status: Loading {model_type}...")
                
                # Create progress dialog
                self.model_progress_dialog = QProgressDialog(
                    f"Đang tải {model_type} model...\n\n" +
                    "Lý do hệ thống đang khựng:\n" +
                    "• Đọc file weights (~100-200MB)\n" +
                    "• Phân tích model architecture\n" +
                    "• Chuyển lên GPU (nếu có)\n\n" +
                    "Vui lòng chờ...",
                    None
                )
                self.model_progress_dialog.setCancelButton(None)
                self.model_progress_dialog.setWindowModality(Qt.WindowModal)
                self.model_progress_dialog.setRange(0, 0)
                self.model_progress_dialog.show()
                
                # Create and start loader thread
                self.model_loader_thread = ModelLoaderThread(model_type, weight_path, device)
                self.model_loader_thread.model_loaded.connect(self._on_model_loaded)
                self.model_loader_thread.load_progress.connect(self._on_model_load_progress)
                self.model_loader_thread.load_error.connect(self._on_model_load_error)
                self.model_loader_thread.start()
            else:
                # Load synchronously (for startup) - ensure model is ready immediately
                print(f"🔄 Loading {model_type} model (sync): {weight_name}...")
                
                model = YOLO(weight_path)
                model.to(device)
                
                self.yolo_model = model
                self.current_model_type = model_type
                self.current_model_config = get_model_config(model_type)
                
                # Update thread model if thread exists
                from core import VideoThread
                if hasattr(self, 'thread') and self.thread is not None and isinstance(self.thread, VideoThread):
                    self.thread.set_model(self.yolo_model)
                    self.thread.model_config = self.current_model_config
                    print(f"✅ Model also set in VideoThread")
                
                # Update spinboxes
                if hasattr(self, 'imgsz_spinbox') and self.current_model_config:
                    self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
                if hasattr(self, 'conf_spinbox') and self.current_model_config:
                    self.conf_spinbox.setValue(self.current_model_config['default_conf'])
                
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"Status: Model ready - {model_type}")
                print(f"✅ Model loaded successfully")
            
            return True
        except Exception as e:
            import traceback
            print(f"❌ Failed to load model: {e}")
            print(traceback.format_exc())
            self.model_loading = False
            if hasattr(self, 'model_progress_dialog'):
                self.model_progress_dialog.close()
            if hasattr(self, 'status_label'):
                QMessageBox.warning(self, "Model Load Error", f"Could not load model:\n{e}")
            return False
    
    def _on_model_loaded(self, model):
        """Callback when model finishes loading"""
        self.model_loading = False
        
        # Close progress dialog
        if hasattr(self, 'model_progress_dialog'):
            self.model_progress_dialog.close()
        
        if model is None:
            if hasattr(self, 'status_label'):
                self.status_label.setText("Status: Model load failed")
            return
        
        self.yolo_model = model
        
        # Update thread model if thread exists
        from core import VideoThread
        if hasattr(self, 'thread') and self.thread is not None and isinstance(self.thread, VideoThread):
            self.thread.set_model(self.yolo_model)
            self.thread.model_config = self.current_model_config
            print(f"✅ Model also set in VideoThread")
        
        # Update spinboxes with model's default values
        if hasattr(self, 'imgsz_spinbox') and self.current_model_config:
            self.imgsz_spinbox.setValue(self.current_model_config['default_imgsz'])
        if hasattr(self, 'conf_spinbox') and self.current_model_config:
            self.conf_spinbox.setValue(self.current_model_config['default_conf'])
        
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Status: Model ready - {self.current_model_type}")
        print(f"✅ Model loaded successfully")
        
        # If user clicked Start Detection while model was loading, auto-start now
        if getattr(self, 'pending_detection_start', False):
            self.pending_detection_start = False
            print("🚀 Auto-starting detection after model load...")
            # Schedule start_detection to run on next event loop iteration
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, self.start_detection)
    
    def _on_model_load_progress(self, message):
        """Callback for model loading progress messages"""
        print(message)
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Status: {message}")
    
    def _on_model_load_error(self, error_message):
        """Callback when model loading fails"""
        self.model_loading = False
        
        # Close progress dialog
        if hasattr(self, 'model_progress_dialog'):
            self.model_progress_dialog.close()
        
        print(error_message)
        if hasattr(self, 'status_label'):
            self.status_label.setText("Status: Model load failed")
        QMessageBox.warning(self, "Model Load Error", error_message)
    
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
            # Load asynchronously when user selects a model (not at startup)
            success = self.load_model(model_type, weight_name, async_mode=True)
            if success:
                # Update spinboxes with model default values (will be set when async load finishes)
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

"""Model Loader Thread - Load YOLO model asynchronously to avoid UI freeze"""

from PyQt5.QtCore import QThread, pyqtSignal
import traceback


class ModelLoaderThread(QThread):
    """Background thread for loading YOLO models asynchronously"""
    
    model_loaded = pyqtSignal(object)  # Emits loaded model
    load_progress = pyqtSignal(str)    # Emits progress messages
    load_error = pyqtSignal(str)       # Emits error messages
    
    def __init__(self, model_type, weight_path, device='cpu'):
        """
        Args:
            model_type: Type of model (e.g., 'YOLOv8')
            weight_path: Path to model weights
            device: Device to load model on ('cpu' or 'cuda:0')
        """
        super().__init__()
        self.model_type = model_type
        self.weight_path = weight_path
        self.device = device
        self.model = None
    
    def run(self):
        """Load model in background thread"""
        try:
            self.load_progress.emit(f"🔄 Loading {self.model_type} model...")
            
            from ultralytics import YOLO
            
            # Load model from weight file
            self.model = YOLO(self.weight_path)
            
            # Move to target device
            self.model.to(self.device)
            
            self.load_progress.emit(f"✅ Model loaded on device: {self.device}")
            self.model_loaded.emit(self.model)
            
        except Exception as e:
            error_msg = f"❌ Failed to load model: {e}\n{traceback.format_exc()}"
            print(error_msg)
            self.load_error.emit(error_msg)
            self.model_loaded.emit(None)

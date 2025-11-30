# src/app/controllers/model_controller.py
"""
ModelController: quét model, load weight và đồng bộ thông số xuống thread.
"""

from PyQt5.QtWidgets import QMessageBox

from model_config import get_model_config, get_weight_path, scan_all_models


class ModelController:
    def __init__(self, state, window):
        self.state = state
        self.window = window

        self.available_models = scan_all_models()
        self.state.available_models = self.available_models

    def init_model_list(self):
        if not hasattr(self.window, "model_type_combo"):
            return

        if getattr(self.state, "available_models", None):
            self.available_models = self.state.available_models

        self.window.model_type_combo.clear()
        for model_type in self.available_models.keys():
            self.window.model_type_combo.addItem(model_type)

        if self.window.model_type_combo.count() > 0:
            self.on_model_type_changed()

    def on_model_type_changed(self):
        if not hasattr(self.window, "weight_combo"):
            return

        self.window.weight_combo.clear()

        idx = self.window.model_type_combo.currentIndex()
        if idx < 0:
            return

        model_type = list(self.available_models.keys())[idx]
        weights = self.available_models[model_type]["weights"]

        for w in weights:
            self.window.weight_combo.addItem(w)

        if weights:
            self.on_weight_changed()

    def on_weight_changed(self):
        idx = self.window.model_type_combo.currentIndex()
        if idx < 0:
            return

        model_type = list(self.available_models.keys())[idx]
        weight_name = self.window.weight_combo.currentText()

        if not weight_name:
            return

        self.load_model(model_type, weight_name)

    def load_model(self, model_type, weight_name):
        try:
            # Lazy import YOLO here to avoid DLL load at module import time
            from ultralytics import YOLO

            weight_path = get_weight_path(model_type, weight_name)
            cfg = get_model_config(model_type)

            print(f"Loading {model_type} - {weight_name}")
            model = YOLO(weight_path)

            # Save to state
            self.state.current_model_type = model_type
            self.state.current_model = model
            self.state.model_config = cfg

            # Update spinboxes
            if hasattr(self.window, "imgsz_spinbox"):
                self.window.imgsz_spinbox.setValue(cfg["default_imgsz"])
            if hasattr(self.window, "conf_spinbox"):
                self.window.conf_spinbox.setValue(cfg["default_conf"])
            if hasattr(self.window, "model_info_label"):
                self.window.model_info_label.setText(f"{model_type} - {weight_name}")

            # Update thread model nếu đã chạy
            if hasattr(self.window, "thread") and self.window.thread:
                self.window.thread.set_model(model)
                self.window.thread.model_config = cfg

            print("Model loaded:", weight_path)
            self.window.status_label.setText(f"Status: Loaded {model_type} - {weight_name}")
            return True

        except Exception as e:
            print("Load model error:", e)
            QMessageBox.warning(self.window, "Model Load Error", str(e))
            return False

    def on_imgsz_changed(self):
        if not self.state.model_config:
            return

        new_val = self.window.imgsz_spinbox.value()
        self.state.model_config["default_imgsz"] = new_val

        if hasattr(self.window, "thread") and self.window.thread:
            self.window.thread.model_config["default_imgsz"] = new_val

        print(f"ImgSize -> {new_val}")

    def on_conf_changed(self):
        if not self.state.model_config:
            return

        new_conf = round(self.window.conf_spinbox.value(), 2)
        self.state.model_config["default_conf"] = new_conf

        if hasattr(self.window, "thread") and self.window.thread:
            self.window.thread.model_config["default_conf"] = new_conf

        print(f"Conf -> {new_conf}")

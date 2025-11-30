# src/app/controllers/detection_controller.py
"""
DetectionController

Chịu trách nhiệm:
- Bật / tắt chế độ detection (YOLO + logic vi phạm)
- Đồng bộ state.detection_running
- Cập nhật UI: nút Start/Stop, menu Detection, status bar
- Reset các set violators khi dừng

Phụ thuộc:
- AppState: current_model, detection_running, violator_track_ids, ...
- MainWindow: thread, btn_start, action_start_detection, status_label
"""

from PyQt5.QtWidgets import QMessageBox


class DetectionController:
    def __init__(self, state, window):
        self.state = state
        self.window = window

    def toggle_detection(self):
        """
        Tương đương hàm start_detection() cũ:
        - Nếu chưa chạy → start
        - Nếu đang chạy → stop
        """
        # Nếu đang tắt → bật
        if not self.state.detection_running:
            self._start_detection()
        else:
            self._stop_detection()

    # =====================================================================
    # START
    # =====================================================================
    def _start_detection(self):
        # 1. Kiểm tra model đã load chưa
        if self.state.current_model is None:
            self.window.status_label.setText("Status: Model not loaded")
            QMessageBox.warning(self.window, "No Model",
                                "Please select/load a model first!")
            return

        # 2. (Optional) Cảnh báo nếu chưa có reference vector mà đã có Direction ROI
        if self.state.reference_vector_p1 is None or self.state.reference_vector_p2 is None:
            if self.state.direction_rois:
                reply = QMessageBox.question(
                    self.window,
                    "⚠️ Reference Vector Not Set",
                    "Reference Vector chưa được thiết lập.\n"
                    "Điều này có thể làm giảm độ chính xác khi xác định hướng rẽ.\n\n"
                    "Bạn có muốn tiếp tục không?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    self.window.status_label.setText(
                        "Status: Please set Reference Vector first"
                    )
                    return

        # 3. Gắn model + config vào thread nếu chưa
        if hasattr(self.window, "thread") and self.window.thread:
            if not getattr(self.window.thread, "model_loaded", False):
                self.window.thread.set_model(self.state.current_model)
                self.window.thread.model_config = self.state.model_config
            self.window.thread.detection_enabled = True

        # 4. Cập nhật state + UI
        self.state.detection_running = True

        if hasattr(self.window, "btn_start"):
            self.window.btn_start.setText("Stop Detection")
        if hasattr(self.window, "action_start_detection"):
            self.window.action_start_detection.setText("Stop Detection")

        self.window.status_label.setText("Status: Detection running...")
        print("🚀 Detection started")

    # =====================================================================
    # STOP
    # =====================================================================
    def _stop_detection(self):
        # 1. Tắt detection ở thread
        if hasattr(self.window, "thread") and self.window.thread:
            self.window.thread.detection_enabled = False

        # 2. Cập nhật state
        self.state.detection_running = False

        # Reset các tập vi phạm / đếm
        self.state.violator_track_ids.clear()
        self.state.red_light_violators.clear()
        self.state.lane_violators.clear()
        self.state.passed_vehicles.clear()
        self.state.motorbike_ids.clear()
        self.state.car_ids.clear()

        # 3. Cập nhật UI
        if hasattr(self.window, "btn_start"):
            self.window.btn_start.setText("Start Detection")
        if hasattr(self.window, "action_start_detection"):
            self.window.action_start_detection.setText("Start Detection")

        self.window.status_label.setText("Status: Detection stopped")
        print("⏹️ Detection stopped")

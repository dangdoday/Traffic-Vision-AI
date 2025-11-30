# src/app/controllers/config_controller.py
"""
Quản lý save/load cấu hình ROI (lane, stopline, traffic light, direction ROI, ref vector).
"""

import math
from PyQt5.QtWidgets import QMessageBox

from app.app_state import AppState
from utils.config_manager import ConfigManager


class ConfigController:
    def __init__(self, state: AppState, window):
        self.state = state
        self.window = window
        self.manager = ConfigManager()

    # =========================================================
    # 1. SAVE CONFIG
    # =========================================================
    def save_configuration(self):
        if not self.window.video_path:
            QMessageBox.warning(
                self.window,
                "No Video",
                "Please load a video first before saving configuration.",
            )
            return

        ref_vec = None
        if self.state.reference_vector_p1 and self.state.reference_vector_p2:
            ref_vec = (
                tuple(self.state.reference_vector_p1),
                tuple(self.state.reference_vector_p2),
            )

        ok = self.manager.save_config(
            video_path=self.window.video_path,
            lane_configs=self.state.lanes,
            stop_line=self.state.stop_line,
            tl_rois=self.state.tl_rois,
            direction_rois=self.state.direction_rois,
            reference_vector=ref_vec,
        )

        if not ok:
            QMessageBox.critical(self.window, "Save Failed", "Failed to save configuration.")
            return

        config_path = self.manager.get_config_path(self.window.video_path)
        QMessageBox.information(
            self.window,
            "Configuration Saved",
            f"All ROIs saved!\n\nFile: {config_path.name}",
        )

        if hasattr(self.window, "config_status_label"):
            self.window.config_status_label.setText("Config: Saved OK")
            self.window.config_status_label.setStyleSheet(
                "QLabel { color: green; font-weight: bold; }"
            )

    # =========================================================
    # 2. LOAD CONFIG MANUAL
    # =========================================================
    def load_configuration(self):
        if not self.window.video_path:
            QMessageBox.warning(self.window, "No Video", "Please load a video first.")
            return

        result = self.manager.load_config(self.window.video_path)
        if result is None:
            QMessageBox.warning(
                self.window,
                "No Config Found",
                "No saved config found for this video.",
            )
            return

        self._apply_loaded_config(result)

        config_path = self.manager.get_config_path(self.window.video_path)
        QMessageBox.information(self.window, "Configuration Loaded", f"Loaded: {config_path.name}")

    # =========================================================
    # 3. AUTO LOAD CONFIG
    # =========================================================
    def auto_load(self):
        result = self.manager.load_config(self.window.video_path)
        if result is None:
            return False
        self._apply_loaded_config(result)
        return True

    # =========================================================
    # 4. APPLY CONFIG
    # =========================================================
    def _apply_loaded_config(self, cfg):
        self.state.lanes = cfg["lanes"]
        self.state.stop_line = cfg["stopline"]
        self.state.tl_rois = cfg["traffic_lights"]
        self.state.direction_rois = cfg["direction_zones"]

        if hasattr(self.window, "lane_controller"):
            self.window.lane_controller.update_lane_list_widget()

        if hasattr(self.window, "direction_controller"):
            self.window.direction_controller.update_direction_roi_list_widget()

        if cfg["reference_vector"]:
            p1 = tuple(cfg["reference_vector"][0])
            p2 = tuple(cfg["reference_vector"][1])

            self.state.reference_vector_p1 = p1
            self.state.reference_vector_p2 = p2

            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            angle = math.degrees(math.atan2(dy, dx))
            self.state.reference_vector_angle = angle

            self.window.ref_vector_label.setText(f"Ref: {angle:.1f} deg")
            self.window.ref_vector_label.setStyleSheet(
                "QLabel { color: green; font-weight: bold; }"
            )

            if hasattr(self.window, "thread") and self.window.thread:
                self.window.thread.set_reference_angle(angle)
        else:
            self.state.reference_vector_p1 = None
            self.state.reference_vector_p2 = None
            self.state.reference_vector_angle = None
            self.window.ref_vector_label.setText("Ref Vector: Not set")
            self.window.ref_vector_label.setStyleSheet(
                "QLabel { color: orange; font-weight: bold; }"
            )

        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

        print("�o. Configuration applied.")

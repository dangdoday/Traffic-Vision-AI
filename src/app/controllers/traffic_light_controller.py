# src/app/controllers/traffic_light_controller.py
"""
TrafficLightController: thêm/xóa ROI đèn giao thông và cập nhật màu theo ROI pixel.
"""

from typing import List, Tuple

import cv2
import numpy as np
from PyQt5.QtWidgets import QInputDialog, QMessageBox

from app.app_state import AppState

ColorStr = str
TLROI = Tuple[int, int, int, int, str, ColorStr]


class TrafficLightController:
    def __init__(self, state: AppState, window):
        self.state = state
        self.window = window
        self.tracking_active: bool = False
        self.color_frame_count: int = 0

    # =========================================================
    # Add ROI (manual)
    # =========================================================
    def start_manual_tl_selection(self):
        if self.window.current_frame is None:
            self.window.status_label.setText("Status: No frame to select ROI from")
            return

        self.state.drawing_mode = "tl_manual"
        self.state.tmp_tl_point = None
        self.window.status_label.setText("Status: Click 2 points to draw TL ROI")
        print("Manual TL ROI mode - click 2 points")

        if hasattr(self.window, "btn_add_tl"):
            try:
                self.window.btn_add_tl.setText("[Selecting...] Cancel")
                self.window.btn_add_tl.clicked.disconnect()
            except Exception:
                pass
            self.window.btn_add_tl.clicked.connect(self.cancel_tl_selection)

    def handle_click(self, x: int, y: int):
        if self.state.drawing_mode != "tl_manual":
            return

        if self.state.tmp_tl_point is None:
            self.state.tmp_tl_point = (x, y)
            print(f"TL ROI point 1: ({x}, {y})")
            self.window.status_label.setText("Status: Click second point for TL ROI")
            return

        p1 = self.state.tmp_tl_point
        p2 = (x, y)
        x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])

        tl_types = ["�`i th��3ng", "trA�n", "r��� trA�i", "r��� ph���i"]
        tl_type, ok = QInputDialog.getItem(
            self.window,
            "Select Traffic Light Type",
            "Chọn loại đèn giao thông:",
            tl_types,
            editable=False,
        )

        if not ok:
            self.state.tmp_tl_point = None
            self.state.drawing_mode = None
            self.window.status_label.setText("Status: TL selection cancelled")
            self._restore_add_button()
            return

        new_tl: TLROI = (x1, y1, x2, y2, tl_type, "unknown")
        self.state.tl_rois.append(new_tl)
        print(f"TL ROI created: ({x1},{y1},{x2},{y2}) Type={tl_type}")

        self.tracking_active = True
        self.state.tmp_tl_point = None
        self.state.drawing_mode = None
        self.window.status_label.setText(
            f"Status: TL {len(self.state.tl_rois)} added ({tl_type})."
        )
        self._restore_add_button()
        self.update_tl_list_widget()

    def cancel_tl_selection(self):
        self.state.tmp_tl_point = None
        self.state.drawing_mode = None
        self.window.status_label.setText("Status: TL selection cancelled")
        self._restore_add_button()

    def _restore_add_button(self):
        if hasattr(self.window, "btn_add_tl"):
            try:
                self.window.btn_add_tl.clicked.disconnect()
            except Exception:
                pass
            self.window.btn_add_tl.setText("Add Traffic Light ROI")
            self.window.btn_add_tl.clicked.connect(self.start_manual_tl_selection)

    # =========================================================
    # Delete
    # =========================================================
    def delete_selected_tl(self):
        if not hasattr(self.window, "tl_list"):
            return

        selected = self.window.tl_list.currentRow()
        if selected < 0 or selected >= len(self.state.tl_rois):
            QMessageBox.warning(self.window, "No TL ROI", "Please select a traffic light ROI to delete.")
            return

        del self.state.tl_rois[selected]
        self.update_tl_list_widget()
        self.window.status_label.setText(f"Status: Deleted TL ROI {selected + 1}")
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    def update_tl_list_widget(self):
        if not hasattr(self.window, "tl_list"):
            return
        self.window.tl_list.clear()
        for idx, roi in enumerate(self.state.tl_rois, start=1):
            x1, y1, x2, y2, tl_type, color = roi
            self.window.tl_list.addItem(
                f"TL {idx}: ({x1},{y1})-({x2},{y2}) {tl_type} color={color}"
            )

    # =========================================================
    # Color tracking
    # =========================================================
    def update_tl_colors(self, frame):
        """
        Cập nhật màu đèn bằng HSV pixel sampling trên frame hiện tại.
        """
        if not self.tracking_active or not self.state.tl_rois:
            return

        h, w, _ = frame.shape
        updated: List[TLROI] = []

        for roi in self.state.tl_rois:
            x1, y1, x2, y2, tl_type, _ = roi
            x1 = max(0, min(w - 1, x1))
            x2 = max(0, min(w - 1, x2))
            y1 = max(0, min(h - 1, y1))
            y2 = max(0, min(h - 1, y2))
            if x2 <= x1 or y2 <= y1:
                updated.append((x1, y1, x2, y2, tl_type, "unknown"))
                continue

            roi_img = frame[y1:y2, x1:x2]
            color = self._classify_color(roi_img)
            updated.append((x1, y1, x2, y2, tl_type, color))

        # Update in place to keep reference used by VideoThread
        self.state.tl_rois[:] = updated
        self.update_tl_list_widget()

    @staticmethod
    def _classify_color(roi) -> ColorStr:
        if roi is None or roi.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(cv2.resize(roi, (32, 32)), cv2.COLOR_BGR2HSV)
        red1 = cv2.inRange(hsv, (0, 100, 80), (10, 255, 255))
        red2 = cv2.inRange(hsv, (160, 100, 80), (180, 255, 255))
        yellow = cv2.inRange(hsv, (15, 100, 80), (35, 255, 255))
        green = cv2.inRange(hsv, (40, 100, 80), (90, 255, 255))

        r = (red1.mean() + red2.mean()) / 510.0
        y = yellow.mean() / 255.0
        g = green.mean() / 255.0

        m = max(r, y, g)
        if m < 0.02:
            return "unknown"
        if r == m:
            return "�`��?"
        if y == m:
            return "vA�ng"
        return "xanh"

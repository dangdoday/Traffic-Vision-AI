# src/app/controllers/direction_roi_controller.py
"""
Direction ROI controller: vẽ/xóa/đổi cấu hình ROI hướng đi.
"""

from typing import List

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from app.app_state import AppState


class DirectionROIController:
    def __init__(self, state: AppState, window):
        self.state = state
        self.window = window
        self.show_direction_rois: bool = True

    # =========================================================
    # Start drawing
    # =========================================================
    def start_add_direction_roi(self):
        if self.window.current_frame is None:
            QMessageBox.warning(
                self.window, "No Frame", "No video frame available. Please load a video first."
            )
            return

        self.state.drawing_mode = "direction_roi"
        self.state.tmp_direction_pts.clear()

        if hasattr(self.window, "btn_finish_direction_roi"):
            self.window.btn_finish_direction_roi.setEnabled(True)

        self.window.status_label.setText(
            "Status: Click points to draw Direction ROI. Click 'Finish' when done."
        )
        print("Direction ROI drawing mode ON")

    def handle_click(self, x: int, y: int):
        if self.state.drawing_mode != "direction_roi":
            return

        self.state.tmp_direction_pts.append((x, y))
        self.window.status_label.setText(
            f"Status: Direction ROI - {len(self.state.tmp_direction_pts)} points."
        )

    # =========================================================
    # Finish drawing
    # =========================================================
    def finish_direction_roi(self):
        if len(self.state.tmp_direction_pts) < 3:
            QMessageBox.warning(self.window, "Invalid ROI", "Direction ROI needs at least 3 points!")
            return

        allowed, primary = self._prompt_allowed_directions()
        if not allowed:
            return

        roi_id = len(self.state.direction_rois) + 1
        new_roi = {
            "name": f"roi_{roi_id}",
            "points": list(self.state.tmp_direction_pts),
            "allowed_directions": allowed,
            "primary_direction": primary,
            "direction": primary,
        }
        self.state.direction_rois.append(new_roi)

        allowed_str = "+".join([d.upper() for d in allowed])
        print(f"Created Direction ROI #{roi_id}: {allowed_str} (primary: {primary})")
        self.window.status_label.setText(f"Status: Added ROI #{roi_id} - Allowed: {allowed_str}")

        self.state.tmp_direction_pts.clear()
        self.state.drawing_mode = None
        if hasattr(self.window, "btn_finish_direction_roi"):
            self.window.btn_finish_direction_roi.setEnabled(False)

        self.update_direction_roi_list_widget()
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    def _prompt_allowed_directions(self) -> tuple[List[str], str]:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Select Allowed Directions")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Chọn các hướng đi được phép trong vùng này:"))

        check_left = QCheckBox("Rẽ trái (Left)")
        check_straight = QCheckBox("Đi thẳng (Straight)")
        check_right = QCheckBox("Rẽ phải (Right)")

        sd = self.state.selected_direction
        if sd == "left":
            check_left.setChecked(True)
        elif sd == "straight":
            check_straight.setChecked(True)
        elif sd == "right":
            check_right.setChecked(True)

        layout.addWidget(check_left)
        layout.addWidget(check_straight)
        layout.addWidget(check_right)

        layout.addWidget(QLabel("\nHướng chính (Primary - dùng để tô màu):"))
        primary_group = QButtonGroup(dialog)
        radio_left = QRadioButton("Left")
        radio_straight = QRadioButton("Straight")
        radio_right = QRadioButton("Right")

        primary_group.addButton(radio_left)
        primary_group.addButton(radio_straight)
        primary_group.addButton(radio_right)

        if sd == "left":
            radio_left.setChecked(True)
        elif sd == "straight":
            radio_straight.setChecked(True)
        elif sd == "right":
            radio_right.setChecked(True)

        layout.addWidget(radio_left)
        layout.addWidget(radio_straight)
        layout.addWidget(radio_right)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        if dialog.exec_() != QDialog.Accepted:
            return [], ""

        allowed: List[str] = []
        if check_left.isChecked():
            allowed.append("left")
        if check_straight.isChecked():
            allowed.append("straight")
        if check_right.isChecked():
            allowed.append("right")

        if not allowed:
            QMessageBox.warning(self.window, "No Direction", "Phải chọn ít nhất 1 hướng!")
            return [], ""

        if radio_left.isChecked():
            primary = "left"
        elif radio_straight.isChecked():
            primary = "straight"
        elif radio_right.isChecked():
            primary = "right"
        else:
            primary = allowed[0]

        return allowed, primary

    # =========================================================
    # Delete ROI
    # =========================================================
    def delete_selected_direction_roi(self):
        if not hasattr(self.window, "direction_roi_list"):
            return

        selected = self.window.direction_roi_list.currentRow()
        if selected < 0 or selected >= len(self.state.direction_rois):
            print("No direction ROI selected to delete")
            return

        del self.state.direction_rois[selected]
        print(f"Direction ROI {selected + 1} deleted")
        self.update_direction_roi_list_widget()
        self.window.status_label.setText(f"Status: Deleted direction ROI {selected + 1}")
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    # =========================================================
    # Change allowed dirs / primary
    # =========================================================
    def change_direction_settings(self):
        if not hasattr(self.window, "direction_roi_list"):
            return

        idx = self.window.direction_roi_list.currentRow()
        if idx < 0 or idx >= len(self.state.direction_rois):
            QMessageBox.warning(self.window, "No ROI", "Please select a direction ROI first.")
            return

        roi = self.state.direction_rois[idx]
        allowed, primary = self._prompt_allowed_directions()
        if not allowed:
            return

        roi["allowed_directions"] = allowed
        roi["primary_direction"] = primary
        roi["direction"] = primary

        allowed_str = "+".join([d.upper() for d in allowed])
        print(f"Updated ROI {idx + 1}: {allowed_str} (primary: {primary})")
        self.window.status_label.setText(
            f"Status: ROI {idx + 1} - Allowed: {allowed_str} (primary {primary})"
        )
        self.update_direction_roi_list_widget()
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    # =========================================================
    # Toggle show/hide
    # =========================================================
    def toggle_from_button(self):
        if not hasattr(self.window, "btn_toggle_direction_rois"):
            return
        self.show_direction_rois = self.window.btn_toggle_direction_rois.isChecked()
        self._sync_toggle_ui()

    def toggle_from_action(self):
        if not hasattr(self.window, "action_toggle_direction_rois"):
            return
        self.show_direction_rois = self.window.action_toggle_direction_rois.isChecked()
        self._sync_toggle_ui()

    def _sync_toggle_ui(self):
        if hasattr(self.window, "btn_toggle_direction_rois"):
            self.window.btn_toggle_direction_rois.setChecked(self.show_direction_rois)
            self.window.btn_toggle_direction_rois.setText(
                "Show Direction ROIs: ON" if self.show_direction_rois else "Show Direction ROIs: OFF"
            )
        if hasattr(self.window, "action_toggle_direction_rois"):
            self.window.action_toggle_direction_rois.setChecked(self.show_direction_rois)

    # =========================================================
    # UI helper
    # =========================================================
    def update_direction_roi_list_widget(self):
        if not hasattr(self.window, "direction_roi_list"):
            return

        self.window.direction_roi_list.clear()
        for idx, roi in enumerate(self.state.direction_rois, start=1):
            allowed = roi.get("allowed_directions", [])
            primary = roi.get("primary_direction", roi.get("direction", "unknown"))
            pts = roi.get("points", [])
            allowed_str = "+".join(allowed) if allowed else "unknown"
            self.window.direction_roi_list.addItem(
                f"ROI {idx}: {len(pts)} pts | allowed {allowed_str} | primary {primary}"
            )

# src/app/controllers/reference_vector_controller.py
"""
Quản lý reference vector (2 điểm trên làn thẳng) để tính góc tham chiếu.
"""

import math
from PyQt5.QtWidgets import QMessageBox


class ReferenceVectorController:
    def __init__(self, state, window):
        self.state = state
        self.window = window

    def begin_set_reference(self):
        self.state.reference_vector_p1 = None
        self.state.reference_vector_p2 = None
        self.state.reference_vector_angle = None
        self.window.status_label.setText(
            "Status: Click 2 points on STRAIGHT lane (start + end)"
        )
        print("Start setting Reference Vector")

    def set_first_point(self, x, y):
        self.state.reference_vector_p1 = (x, y)
        self.window.status_label.setText("Status: Click END point on straight lane")

    def set_second_point(self, x, y):
        self.state.reference_vector_p2 = (x, y)
        self.window.status_label.setText("Status: Press 'Finish Reference Vector' or click Finish")

    def finish_reference(self):
        p1 = self.state.reference_vector_p1
        p2 = self.state.reference_vector_p2

        if p1 is None or p2 is None:
            QMessageBox.warning(self.window, "Incomplete", "Need 2 points for reference vector!")
            return

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)

        if length < 10:
            QMessageBox.warning(
                self.window,
                "Too Short",
                "Reference vector too short! Choose points farther apart.",
            )
            return

        angle = math.degrees(math.atan2(dy, dx))
        self.state.reference_vector_angle = angle

        self.window.ref_vector_label.setText(f"Ref Vector: {angle:.1f} deg ({dx:.0f},{dy:.0f})")
        self.window.ref_vector_label.setStyleSheet(
            "QLabel { color: green; font-weight: bold; }"
        )

        if hasattr(self.window, "thread") and self.window.thread:
            self.window.thread.set_reference_angle(angle)
            print(f"Applied ref_angle={angle:.1f} deg to VehicleTracker")

        self.window.status_label.setText(f"Status: Reference vector set ({angle:.1f} deg)")

        QMessageBox.information(
            self.window,
            "Reference Vector Set",
            f"Reference vector set successfully!\n\n"
            f"Angle: {angle:.1f} deg\n"
            f"This will be used to calculate vehicle turning directions.",
        )

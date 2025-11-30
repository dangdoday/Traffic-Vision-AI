from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QDialog,
    QCheckBox, QDialogButtonBox, QApplication)
import sys

VEHICLE_TYPES = ["o to", "xe bus", "xe dap", "xe may", "xe tai"]

class VehicleTypeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn loại phương tiện cho lane")
        layout = QVBoxLayout()
        self.checkboxes = []
        for vt in VEHICLE_TYPES:
            cb = QCheckBox(vt)
            layout.addWidget(cb)
            self.checkboxes.append(cb)
        self.cb_all = QCheckBox("Tất cả các loại xe")
        layout.addWidget(self.cb_all)
        self.cb_all.stateChanged.connect(self.toggle_all)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def toggle_all(self, state):
        for cb in self.checkboxes:
            cb.setChecked(state == 2)
            cb.setEnabled(state != 2)

    def get_selected(self):
        if self.cb_all.isChecked():
            return ["all"]
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class LaneSelectorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chọn Lane và Loại Phương Tiện")
        self.layout = QVBoxLayout()
        self.label = QLabel("Nhấn nút để chọn lane, sau đó chọn loại phương tiện.")
        self.layout.addWidget(self.label)
        self.btn_select_lane = QPushButton("Chọn Lane")
        self.btn_select_lane.clicked.connect(self.select_lane)
        self.layout.addWidget(self.btn_select_lane)
        self.setLayout(self.layout)
        self.lanes = []

    def select_lane(self):
        # Giả lập: sau khi vẽ xong lane, hiện dialog chọn loại xe
        dialog = VehicleTypeDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            allowed = dialog.get_selected()
            self.lanes.append({"poly": [(0,0),(1,1),(2,2)], "allowed_labels": allowed})
            self.label.setText(f"Đã chọn lane với loại xe: {allowed}")
        else:
            self.label.setText("Hủy chọn lane.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LaneSelectorWindow()
    win.show()
    sys.exit(app.exec_())
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QListWidget, QMessageBox

class LaneSelector(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lane Selector")
        self.setGeometry(100, 100, 400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.lane_list = QListWidget()
        self.update_lane_list()
        layout.addWidget(self.lane_list)

        add_button = QPushButton("Add Lane")
        add_button.clicked.connect(self.add_lane)
        layout.addWidget(add_button)

        delete_button = QPushButton("Delete Lane")
        delete_button.clicked.connect(self.delete_lane)
        layout.addWidget(delete_button)

        self.setLayout(layout)

    def update_lane_list(self):
        self.lane_list.clear()
        lanes = self.lane_controller.get_lanes()
        for idx, lane in enumerate(lanes):
            self.lane_list.addItem(f"Lane {idx} - Points: {lane['poly']}")

    def add_lane(self):
        # Logic to add a lane (e.g., open a dialog to get lane points)
        # For now, we will just simulate adding a lane
        dialog = VehicleTypeDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            allowed = dialog.get_selected()
            example_points = [(100, 100), (200, 200), (300, 100)]  # Example points
            if self.lane_controller.add_lane(example_points, allowed):
                self.update_lane_list()
                QMessageBox.information(self, "Success", f"Lane added with vehicle types: {allowed}")

    def delete_lane(self):
        selected_items = self.lane_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a lane to delete.")
            return

        selected_item = selected_items[0]
        lane_id = int(selected_item.text().split()[1])  # Extract lane ID from the text
        if self.lane_controller.delete_lane(lane_id):
            self.update_lane_list()
            QMessageBox.information(self, "Success", "Lane deleted successfully!")
        else:
            QMessageBox.warning(self, "Error", "Failed to delete lane.")

# To run the LaneSelector independently for testing
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = LaneSelector()
    window.show()
    sys.exit(app.exec_())
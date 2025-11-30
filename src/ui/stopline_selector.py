from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QListWidget, QMessageBox
from PyQt5.QtCore import Qt

class StopLineSelector(QWidget):
    def __init__(self, stop_line_controller=None):
        super().__init__()
        self.stop_line_controller = stop_line_controller
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Stop Line Selector")
        self.setGeometry(100, 100, 300, 400)

        layout = QVBoxLayout()

        self.stop_line_list = QListWidget()
        layout.addWidget(self.stop_line_list)

        add_button = QPushButton("Add Stop Line")
        add_button.clicked.connect(self.add_stop_line)
        layout.addWidget(add_button)

        delete_button = QPushButton("Delete Stop Line")
        delete_button.clicked.connect(self.delete_stop_line)
        layout.addWidget(delete_button)

        self.setLayout(layout)

    def add_stop_line(self):
        # Logic to add a stop line
        # This should open a dialog or a new window to select points for the stop line
        # For now, we will just simulate adding a stop line
        stop_line_id = self.stop_line_controller.add_stop_line()
        self.stop_line_list.addItem(f"Stop Line {stop_line_id}")

    def delete_stop_line(self):
        selected_items = self.stop_line_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a stop line to delete.")
            return
        
        for item in selected_items:
            stop_line_id = int(item.text().split()[-1])
            self.stop_line_controller.delete_stop_line(stop_line_id)
            self.stop_line_list.takeItem(self.stop_line_list.row(item))

    def update_stop_line_list(self):
        self.stop_line_list.clear()
        for stop_line in self.stop_line_controller.get_all_stop_lines():
            self.stop_line_list.addItem(f"Stop Line {stop_line.id}")
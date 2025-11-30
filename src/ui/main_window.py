from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QMessageBox
from ui.lane_selector import LaneSelector
from ui.stopline_selector import StopLineSelector
from controllers.stopline_controller import StopLineController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traffic Violation Detector")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.lane_selector = LaneSelector()
        self.stopline_selector = StopLineSelector(None)
        self.stopline_controller = StopLineController(self.stopline_selector)

        self.layout.addWidget(QLabel("Lane Management"))
        self.layout.addWidget(self.lane_selector)

        self.layout.addWidget(QLabel("Stop Line Management"))
        self.layout.addWidget(self.stopline_selector)

        self.setup_buttons()

    def setup_buttons(self):
        self.add_lane_button = QPushButton("Add Lane")
        self.add_lane_button.clicked.connect(self.add_lane)
        self.layout.addWidget(self.add_lane_button)

        self.delete_lane_button = QPushButton("Delete Lane")
        self.delete_lane_button.clicked.connect(self.delete_lane)
        self.layout.addWidget(self.delete_lane_button)

        self.add_stopline_button = QPushButton("Add Stop Line")
        self.add_stopline_button.clicked.connect(self.add_stopline)
        self.layout.addWidget(self.add_stopline_button)

        self.delete_stopline_button = QPushButton("Delete Stop Line")
        self.delete_stopline_button.clicked.connect(self.delete_stopline)
        self.layout.addWidget(self.delete_stopline_button)

    def add_lane(self):
        self.lane_selector.add_lane()

    def delete_lane(self):
        self.lane_selector.delete_lane()

    def add_stopline(self):
        self.stopline_selector.add_stop_line()

    def delete_stopline(self):
        self.stopline_selector.delete_stop_line()
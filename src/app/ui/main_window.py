# src/app/ui/main_window.py

import sys
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.app_state import AppState
from app.controllers.config_controller import ConfigController
from app.controllers.detection_controller import DetectionController
from app.controllers.direction_roi_controller import DirectionROIController
from app.controllers.lane_controller import LaneController
from app.controllers.model_controller import ModelController
from app.controllers.reference_vector_controller import ReferenceVectorController
from app.controllers.traffic_light_controller import TrafficLightController
from app.detection import (
    calculate_vehicle_direction,
    check_lane_direction_match,
    check_speed_violation,
    check_tl_violation,
    estimate_vehicle_speed,
)
from app.geometry import is_on_stop_line, point_in_polygon
from core.video_thread import VideoThread
from model_config import migrate_old_weights, scan_all_models
from tools.roi_editor import ROIEditor
from ui.overlay_drawer import OverlayDrawer
from utils.config_manager import ConfigManager

VEHICLE_CLASSES = {
    0: "o to",
    1: "xe bus",
    2: "xe dap",
    3: "xe may",
    4: "xe tai",
}
ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4]


class MainWindow(QMainWindow):
    def __init__(self, video_path: str = ""):
        super().__init__()

        # State & helpers
        self.state = AppState()
        self.roi_editor = ROIEditor()
        self.config_manager = ConfigManager()
        self.overlay = OverlayDrawer(alpha=0.3)

        self.yolo_model = None
        self.current_frame = None
        self.thread: VideoThread | None = None
        self.video_path = video_path

        # Scale info for click mapping
        self.current_display_scale = 1.0
        self.current_display_width = 0
        self.current_display_height = 0
        self.current_display_offset_x = 0
        self.current_display_offset_y = 0

        # UI/Controllers
        self._init_ui()
        self._init_menu_bar()
        self._init_controllers()

        # Scan models once
        migrate_old_weights()
        self.state.available_models = scan_all_models()
        self.model_controller.available_models = self.state.available_models
        self.model_controller.init_model_list()

        # Load initial video
        if self.video_path:
            self.load_video(self.video_path)
        else:
            self.select_video_on_start()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("Traffic Vision AI")
        self.setGeometry(50, 50, 1700, 950)

        main_layout = QHBoxLayout()

        # Video label
        self.video_label = QLabel()
        self.video_label.setScaledContents(False)
        self.video_label.setMinimumSize(1024, 768)
        self.video_label.mousePressEvent = self.on_video_click
        main_layout.addWidget(self.video_label)

        # Right control panel
        control_layout = QVBoxLayout()

        # Model selection
        control_layout.addWidget(QLabel("Model Selection"))
        self.model_type_combo = QComboBox()
        self.weight_combo = QComboBox()
        self.model_info_label = QLabel("No model loaded")
        control_layout.addWidget(self.model_type_combo)
        control_layout.addWidget(self.weight_combo)
        control_layout.addWidget(self.model_info_label)

        # Detection params
        control_layout.addWidget(QLabel("Detection Parameters"))
        imgsz_layout = QHBoxLayout()
        imgsz_layout.addWidget(QLabel("ImgSize:"))
        self.imgsz_spinbox = QSpinBox()
        self.imgsz_spinbox.setRange(160, 1920)
        imgsz_layout.addWidget(self.imgsz_spinbox)
        control_layout.addLayout(imgsz_layout)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        self.conf_spinbox = QDoubleSpinBox()
        self.conf_spinbox.setRange(0.05, 0.99)
        self.conf_spinbox.setSingleStep(0.01)
        conf_layout.addWidget(self.conf_spinbox)
        control_layout.addLayout(conf_layout)

        # Lanes
        control_layout.addWidget(QLabel("Lane Management"))
        self.lane_list = QListWidget()
        control_layout.addWidget(self.lane_list)
        self.btn_add_lane = QPushButton("Add Lane (Click on video)")
        self.btn_delete_lane = QPushButton("Delete Selected Lane")
        control_layout.addWidget(self.btn_add_lane)
        control_layout.addWidget(self.btn_delete_lane)

        # Stop line
        control_layout.addWidget(QLabel("Stop Line"))
        self.btn_add_stopline = QPushButton("Set Stop Line (2 points)")
        self.btn_delete_stopline = QPushButton("Delete Stop Line")
        control_layout.addWidget(self.btn_add_stopline)
        control_layout.addWidget(self.btn_delete_stopline)

        # Traffic lights
        control_layout.addWidget(QLabel("Traffic Lights"))
        self.tl_list = QListWidget()
        control_layout.addWidget(self.tl_list)
        self.btn_add_tl = QPushButton("Add Traffic Light ROI")
        self.btn_delete_tl = QPushButton("Delete Selected TL ROI")
        control_layout.addWidget(self.btn_add_tl)
        control_layout.addWidget(self.btn_delete_tl)

        # Direction ROIs
        control_layout.addWidget(QLabel("Direction ROIs"))
        self.direction_roi_list = QListWidget()
        control_layout.addWidget(self.direction_roi_list)
        self.btn_add_direction_roi = QPushButton("Draw Direction ROI")
        self.btn_finish_direction_roi = QPushButton("Finish Direction ROI")
        self.btn_delete_direction_roi = QPushButton("Delete Selected Direction ROI")
        self.btn_change_direction_roi = QPushButton("Change Allowed Directions")
        self.btn_toggle_direction_rois = QPushButton("Show Direction ROIs: ON")
        self.btn_toggle_direction_rois.setCheckable(True)
        self.btn_toggle_direction_rois.setChecked(True)
        control_layout.addWidget(self.btn_add_direction_roi)
        control_layout.addWidget(self.btn_finish_direction_roi)
        control_layout.addWidget(self.btn_delete_direction_roi)
        control_layout.addWidget(self.btn_change_direction_roi)
        control_layout.addWidget(self.btn_toggle_direction_rois)

        # Reference vector
        self.ref_vector_label = QLabel("Ref Vector: Not set")
        self.btn_set_ref_vector = QPushButton("Set Reference Vector (2 points)")
        self.btn_finish_ref_vector = QPushButton("Finish Reference Vector")
        control_layout.addWidget(self.ref_vector_label)
        control_layout.addWidget(self.btn_set_ref_vector)
        control_layout.addWidget(self.btn_finish_ref_vector)

        # Detection
        self.btn_start = QPushButton("Start Detection")
        self.btn_start.setCheckable(False)
        self.btn_toggle_bb = QPushButton("Show All Boxes: ON")
        self.btn_toggle_bb.setCheckable(True)
        self.btn_toggle_bb.setChecked(True)
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_toggle_bb)

        # Config buttons
        control_layout.addWidget(QLabel("Configuration"))
        self.btn_save_config = QPushButton("Save All ROIs Configuration")
        self.btn_load_config = QPushButton("Load Configuration")
        self.config_status_label = QLabel("Config: Not loaded")
        control_layout.addWidget(self.btn_save_config)
        control_layout.addWidget(self.btn_load_config)
        control_layout.addWidget(self.config_status_label)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.status_label = QLabel("Status: Ready")
        self.statusBar().addWidget(self.status_label)

    def _init_menu_bar(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        act_open = QAction("Open Video...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.select_video_on_start)
        file_menu.addAction(act_open)

        act_save_cfg = QAction("Save Config", self)
        act_save_cfg.triggered.connect(self.on_save_config)
        file_menu.addAction(act_save_cfg)

        act_load_cfg = QAction("Load Config", self)
        act_load_cfg.triggered.connect(self.on_load_config)
        file_menu.addAction(act_load_cfg)

        file_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Detection
        det_menu = menubar.addMenu("&Detection")
        self.action_start_detection = QAction("Start Detection", self)
        self.action_start_detection.setShortcut("Space")
        self.action_start_detection.triggered.connect(self.on_toggle_detection_clicked)
        det_menu.addAction(self.action_start_detection)

        # View
        view_menu = menubar.addMenu("&View")
        act_toggle_bb = QAction("Toggle Show All Boxes", self, checkable=True)
        act_toggle_bb.setChecked(True)
        act_toggle_bb.triggered.connect(lambda checked: self.toggle_bbox_display())
        view_menu.addAction(act_toggle_bb)

    def _init_controllers(self):
        self.lane_controller = LaneController(self.state, self)
        self.direction_controller = DirectionROIController(self.state, self)
        self.tl_controller = TrafficLightController(self.state, self)
        self.config_controller = ConfigController(self.state, self)
        self.model_controller = ModelController(self.state, self)
        self.detection_controller = DetectionController(self.state, self)
        self.ref_vector_controller = ReferenceVectorController(self.state, self)

        # Model combo events
        self.model_type_combo.currentIndexChanged.connect(self.model_controller.on_model_type_changed)
        self.weight_combo.currentIndexChanged.connect(self.model_controller.on_weight_changed)
        self.imgsz_spinbox.valueChanged.connect(self.model_controller.on_imgsz_changed)
        self.conf_spinbox.valueChanged.connect(self.model_controller.on_conf_changed)

        # Lane buttons
        self.btn_add_lane.clicked.connect(self.lane_controller.start_add_lane)
        self.btn_delete_lane.clicked.connect(self.lane_controller.delete_selected_lane)

        # Stopline
        self.btn_add_stopline.clicked.connect(self.start_stopline_draw)
        self.btn_delete_stopline.clicked.connect(self.delete_stopline)

        # Traffic lights
        self.btn_add_tl.clicked.connect(self.tl_controller.start_manual_tl_selection)
        self.btn_delete_tl.clicked.connect(self.tl_controller.delete_selected_tl)

        # Direction ROIs
        self.btn_add_direction_roi.clicked.connect(self.direction_controller.start_add_direction_roi)
        self.btn_finish_direction_roi.clicked.connect(self.direction_controller.finish_direction_roi)
        self.btn_finish_direction_roi.setEnabled(False)
        self.btn_delete_direction_roi.clicked.connect(self.direction_controller.delete_selected_direction_roi)
        self.btn_change_direction_roi.clicked.connect(self.direction_controller.change_direction_settings)
        self.btn_toggle_direction_rois.clicked.connect(self.direction_controller.toggle_from_button)

        # Reference vector
        self.btn_set_ref_vector.clicked.connect(self.begin_reference_vector)
        self.btn_finish_ref_vector.clicked.connect(self.finish_reference_vector)

        # Detection
        self.btn_start.clicked.connect(self.on_toggle_detection_clicked)
        self.btn_toggle_bb.clicked.connect(self.toggle_bbox_display)

        # Config
        self.btn_save_config.clicked.connect(self.on_save_config)
        self.btn_load_config.clicked.connect(self.on_load_config)

    # ------------------------------------------------------------------
    # Video handling
    # ------------------------------------------------------------------
    def select_video_on_start(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)",
        )
        if not file_path:
            return
        self.load_video(file_path)

    def load_video(self, file_path: str):
        if not file_path:
            return

        # Stop previous thread
        if self.thread:
            self.thread.stop()
            self.thread.wait()

        self.video_path = file_path
        self.state.video_path = file_path
        self.state.reset_detection_state()

        self.thread = VideoThread(file_path)
        self.thread.change_pixmap_signal.connect(self.update_frame)
        self.thread.error_signal.connect(self.show_error)

        self._apply_thread_globals()

        # Attach model if available
        if self.state.current_model is not None:
            self.thread.set_model(self.state.current_model)
            self.thread.model_config = self.state.model_config

        self.thread.start()

        # Try auto load config
        loaded = self.config_controller.auto_load()
        if loaded:
            self.status_label.setText(f"Status: Loaded {Path(file_path).name} + config")
        else:
            self.status_label.setText(f"Status: Loaded {Path(file_path).name}")

    # ------------------------------------------------------------------
    # Thread globals mapping
    # ------------------------------------------------------------------
    def _apply_thread_globals(self):
        if not self.thread:
            return

        self.thread.set_globals_reference(
            {
                "ALLOWED_VEHICLE_IDS": ALLOWED_VEHICLE_IDS,
                "VEHICLE_CLASSES": VEHICLE_CLASSES,
                "LANE_CONFIGS": self.state.lanes,
                "TL_ROIS": self.state.tl_rois,
                "DIRECTION_ROIS": self.state.direction_rois,
                "get_show_all_boxes": lambda: self.state.show_all_boxes,
                "is_on_stop_line": lambda cx, cy: is_on_stop_line(
                    cx, cy, self.state.stop_line, threshold=15
                ),
                "check_tl_violation": lambda track_id, direction: check_tl_violation(
                    track_id, direction, self.state.tl_rois, self.state.vehicle_directions
                ),
                "point_in_polygon": point_in_polygon,
                "VIOLATOR_TRACK_IDS": self.state.violator_track_ids,
                "RED_LIGHT_VIOLATORS": self.state.red_light_violators,
                "LANE_VIOLATORS": self.state.lane_violators,
                "PASSED_VEHICLES": self.state.passed_vehicles,
                "MOTORBIKE_COUNT": self.state.motorbike_ids,
                "CAR_COUNT": self.state.car_ids,
                "VEHICLE_POSITIONS": self.state.vehicle_positions,
                "VEHICLE_DIRECTIONS": self.state.vehicle_directions,
                "calculate_vehicle_direction": lambda tid, pos, ref_angle=None: calculate_vehicle_direction(
                    tid, pos, self.state.vehicle_positions, ref_angle
                ),
                "estimate_vehicle_speed": lambda tid, fps=30, px2m=0.05: estimate_vehicle_speed(
                    tid, self.state.vehicle_positions, fps, px2m
                ),
                "check_speed_violation": check_speed_violation,
                "check_lane_direction_match": lambda vdir, roi_idx: check_lane_direction_match(
                    vdir, roi_idx, self.state.direction_rois
                ),
            }
        )

    # ------------------------------------------------------------------
    # Frame update + overlays
    # ------------------------------------------------------------------
    def update_frame(self, frame: np.ndarray):
        self.current_frame = frame.copy()
        display = frame.copy()

        # Update TL colors occasionally
        self.tl_controller.update_tl_colors(display)

        # Draw lanes
        if self.state.lanes:
            overlay = display.copy()
            for idx, lane in enumerate(self.state.lanes, start=1):
                poly = lane.get("poly", [])
                if len(poly) < 3:
                    continue
                pts = np.array(poly, dtype=np.int32)
                cv2.fillPoly(overlay, [pts], (255, 0, 0))
                cv2.polylines(display, [pts], True, (255, 0, 0), 2)
                cx = int(np.mean([p[0] for p in poly]))
                cy = int(np.mean([p[1] for p in poly]))
                cv2.putText(
                    display,
                    f"L{idx}",
                    (cx - 10, cy),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )
            display = cv2.addWeighted(overlay, 0.25, display, 0.75, 0)

        # Stop line
        if self.state.stop_line is not None:
            p1, p2 = self.state.stop_line
            cv2.line(display, p1, p2, (0, 0, 255), 4)
            cv2.putText(
                display,
                "STOP LINE",
                (p1[0], max(0, p1[1] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        # Direction ROIs
        if self.direction_controller.show_direction_rois:
            display = self.overlay.draw_direction_rois(display, self.state.direction_rois)

        # Traffic lights
        display = self.overlay.draw_traffic_lights(display, self.state.tl_rois)

        # Reference vector
        display = self.overlay.draw_reference_vector(
            display, self.state.reference_vector_p1, self.state.reference_vector_p2
        )

        # Temp drawings
        display = self.overlay.draw_temporary_lane(display, self.state.tmp_lane_pts)
        display = self.overlay.draw_temporary_direction_roi(
            display, self.state.tmp_direction_pts, self.state.selected_direction
        )
        display = self.overlay.draw_temporary_tl_point(display, self.state.tmp_tl_point)

        if self.state.drawing_mode == "stopline":
            display = self.overlay.draw_temporary_stopline_point(display, self.state.tmp_stop_point)

        # Convert to pixmap
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled = QPixmap.fromImage(qt_img).scaled(
            self.video_label.width(),
            self.video_label.height(),
            Qt.KeepAspectRatio,
        )

        # Store scale for click mapping
        self.current_display_scale = min(
            self.video_label.width() / w, self.video_label.height() / h
        )
        self.current_display_width = int(w * self.current_display_scale)
        self.current_display_height = int(h * self.current_display_scale)
        self.current_display_offset_x = (self.video_label.width() - self.current_display_width) // 2
        self.current_display_offset_y = (self.video_label.height() - self.current_display_height) // 2

        self.video_label.setPixmap(scaled)

    # ------------------------------------------------------------------
    # Mouse click handling
    # ------------------------------------------------------------------
    def on_video_click(self, event):
        if self.current_frame is None:
            return

        x = int((event.x() - self.current_display_offset_x) / self.current_display_scale)
        y = int((event.y() - self.current_display_offset_y) / self.current_display_scale)

        h, w, _ = self.current_frame.shape
        if x < 0 or y < 0 or x >= w or y >= h:
            return

        mode = self.state.drawing_mode
        if mode == "lane":
            self.lane_controller.handle_lane_click(x, y)
        elif mode == "stopline":
            if self.state.tmp_stop_point is None:
                self.state.tmp_stop_point = (x, y)
                self.status_label.setText("Status: Stopline point 1 set. Click second point.")
            else:
                p1 = self.state.tmp_stop_point
                p2 = (x, y)
                self.state.stop_line = (p1, p2)
                self.state.tmp_stop_point = None
                self.state.drawing_mode = None
                self.status_label.setText("Status: Stop line set.")
                self.btn_add_stopline.setText("Set Stop Line (2 points)")
                self._apply_thread_globals()
        elif mode == "direction_roi":
            self.direction_controller.handle_click(x, y)
        elif mode == "tl_manual":
            self.tl_controller.handle_click(x, y)
            self._apply_thread_globals()
        elif mode == "ref_vector":
            if self.state.reference_vector_p1 is None:
                self.ref_vector_controller.set_first_point(x, y)
            else:
                self.ref_vector_controller.set_second_point(x, y)
                self.finish_reference_vector()
        else:
            # Future: handle edit actions
            pass

    # ------------------------------------------------------------------
    # Stop line helpers
    # ------------------------------------------------------------------
    def start_stopline_draw(self):
        self.state.drawing_mode = "stopline"
        self.state.tmp_stop_point = None
        self.status_label.setText("Status: Click 2 points on video to set stop line.")
        self.btn_add_stopline.setText("[Selecting...] Stop Line")

    def delete_stopline(self):
        self.state.stop_line = None
        self.state.tmp_stop_point = None
        self.state.drawing_mode = None
        self.status_label.setText("Status: Stop line cleared.")
        self.btn_add_stopline.setText("Set Stop Line (2 points)")
        self._apply_thread_globals()

    # ------------------------------------------------------------------
    # Reference vector helpers
    # ------------------------------------------------------------------
    def begin_reference_vector(self):
        self.state.drawing_mode = "ref_vector"
        self.ref_vector_controller.begin_set_reference()

    def finish_reference_vector(self):
        self.state.drawing_mode = None
        self.ref_vector_controller.finish_reference()
        if self.state.reference_vector_angle is None and self.state.reference_vector_p1 and self.state.reference_vector_p2:
            dx = self.state.reference_vector_p2[0] - self.state.reference_vector_p1[0]
            dy = self.state.reference_vector_p2[1] - self.state.reference_vector_p1[1]
            self.state.reference_vector_angle = np.degrees(np.arctan2(dy, dx))
        self._apply_thread_globals()

    # ------------------------------------------------------------------
    # Detection / toggles
    # ------------------------------------------------------------------
    def on_toggle_detection_clicked(self):
        self.detection_controller.toggle_detection()
        if self.state.detection_running:
            self.btn_start.setText("Stop Detection")
            self.action_start_detection.setText("Stop Detection")
        else:
            self.btn_start.setText("Start Detection")
            self.action_start_detection.setText("Start Detection")
        if self.thread:
            self.thread.detection_enabled = self.state.detection_running

    def toggle_bbox_display(self):
        self.state.show_all_boxes = self.btn_toggle_bb.isChecked()
        if self.state.show_all_boxes:
            self.btn_toggle_bb.setText("Show All Boxes: ON")
            self.statusBar().showMessage("Status: Showing all vehicles")
        else:
            self.btn_toggle_bb.setText("Show Only Violators: ON")
            self.statusBar().showMessage("Status: Showing only violators")

    # ------------------------------------------------------------------
    # Config actions
    # ------------------------------------------------------------------
    def on_save_config(self):
        self.config_controller.save_configuration()

    def on_load_config(self):
        self.config_controller.load_configuration()
        self._apply_thread_globals()

    # ------------------------------------------------------------------
    # Error & close
    # ------------------------------------------------------------------
    def show_error(self, error_msg):
        self.status_label.setText(f"Status: Error - {error_msg}")
        print(f"Error: {error_msg}")

    def closeEvent(self, event):
        if self.thread:
            self.thread.stop()
            self.thread.wait()
        event.accept()


def main():
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

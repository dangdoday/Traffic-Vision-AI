import sys
import cv2
import numpy as np
import os
import math
import warnings

# Ensure console encoding cannot crash on Windows terminals that do not support UTF-8/emoji
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # If reconfigure is unavailable, fall back silently
    pass

# Suppress minor warnings from dependencies
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='.*Could not find files.*')

# CRITICAL: Import YOLO BEFORE PyQt to avoid DLL conflicts
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully before PyQt")
    YOLO_AVAILABLE = True
except Exception as e:
    print(f"❌ YOLO import failed: {e}")
    YOLO_AVAILABLE = False

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QFileDialog, QInputDialog, QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox, QMenu, QAction, QMenuBar, QDialog, QSlider
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QCursor
from ui.lane_selector import VehicleTypeDialog
import torch

# Check CUDA availability
CUDA_AVAILABLE = torch.cuda.is_available()
if CUDA_AVAILABLE:
    print(f"✅ CUDA available: {torch.cuda.get_device_name(0)}")
else:
    print("⚠️ CUDA not available, will use CPU")

from model_config import scan_all_models, get_weight_path, get_model_config, migrate_old_weights

# =============================================================================
# CRITICAL: Import ALL local modules BEFORE 'core' module
# PaddleOCR (imported by core.video_thread) adds its own 'tools', 'utils', etc. 
# to sys.path, causing import conflicts with our local packages
# =============================================================================

# Import ROI Editor
from tools.roi_editor import ROIEditor

# Import Config Manager
from utils.config_manager import ConfigManager

# Import handlers
from handlers import (
    DirectionROIHandlerMixin, ReferenceVectorHandlerMixin, TrafficLightHandlerMixin, 
    LaneHandlerMixin, ConfigHandlerMixin, EventHandlerMixin, ModelHandlerMixin,
    DisplayHandlerMixin, DialogHandlerMixin, VideoHandlerMixin, DetectionHandlerMixin
)

# Import new modular functions
from app.geometry import point_in_polygon, point_to_segment_distance, is_on_stop_line
from app.detection import (
    tl_pixel_state, classify_tl_color,
    calculate_vehicle_direction, estimate_vehicle_speed,
    check_tl_violation, check_speed_violation, check_lane_direction_match,
    set_vehicle_positions_ref, set_violation_checker_globals
)

# =============================================================================
# NOW import core modules (this will trigger PaddleOCR import)
# =============================================================================

# Import core OOP modules
from core import VehicleTracker, ViolationDetector, StopLineManager, TrafficLightManager, VideoThread

# Import Direction Detection modules
from core.roi_direction_manager import ROIDirectionManager
from core.trajectory_direction_analyzer import TrajectoryDirectionAnalyzer
from core.direction_fusion import DirectionFusion

# Traffic light state - Support multiple traffic lights with types
TL_ROIS = []  # List of (x1, y1, x2, y2, tl_type, current_color) tuples - NO stoplines needed
# tl_type: 'đi thẳng', 'tròn', 'rẽ trái', 'rẽ phải'

# Direction Detection ROIs
# Format: {'name': 'roi_1', 'points': [[x,y], ...], 'allowed_directions': ['left', 'straight'], 'primary_direction': 'straight'}
DIRECTION_ROIS = []  
_tmp_direction_roi_pts = []  # Temporary points while drawing direction ROI
_selected_direction = 'straight'  # Current selected direction for drawing
_selected_directions_multi = ['straight']  # Multiple directions allowed (for complex lanes)

# ROI Editing variables
_editing_roi_index = None  # Index of ROI being edited (None = not editing)
_editing_roi_type = None  # 'lane', 'direction', or 'tl'
_dragging_point_index = None  # Index of point being dragged
_hover_point_index = None  # Index of point being hovered
_hover_edge_indices = None  # (point1_idx, point2_idx) of edge being hovered for insertion

# Vehicle tracking for direction detection
VEHICLE_POSITIONS = {}  # {track_id: [(x, y, timestamp), ...]} - last N positions for direction calc
VEHICLE_DIRECTIONS = {}  # {track_id: 'straight', 'left', 'right', 'unknown'}

# Link VEHICLE_POSITIONS to direction_detector module
set_vehicle_positions_ref(VEHICLE_POSITIONS)

# ⚠️ NOTE: set_violation_checker_globals is now called in MainWindow.__init__()
# to ensure proper module context (avoids issues when module is imported vs run directly)
# OLD CODE (moved to MainWindow.__init__):
# set_violation_checker_globals(TL_ROIS, DIRECTION_ROIS, VEHICLE_DIRECTIONS)

# NOTE: tl_pixel_state, classify_tl_color, point_in_polygon are imported from modules
# See imports at top of file:
#   from app.geometry import point_in_polygon, point_to_segment_distance, is_on_stop_line
#   from app.detection import tl_pixel_state, classify_tl_color, ...

# Global variables
LANE_CONFIGS = []
STOP_LINE = None  # Single stopline: (p1, p2)
_tmp_lane_pts = []
_tmp_stop_point = None
_tmp_tl_point = None  # For manual TL ROI selection
_drawing_mode = None  # 'lane' or 'stopline' or 'tl_manual' or 'direction_roi' or 'ref_vector' or None
_detection_running = False
_show_all_boxes = True  # True = show all vehicles, False = show only violators

# Detection variables
VIOLATOR_TRACK_IDS = set()
RED_LIGHT_VIOLATORS = set()
LANE_VIOLATORS = set()
DIRECTION_VIOLATORS = set()  # Track vehicles that went wrong direction in ROI
PASSED_VEHICLES = set()  # Track vehicles that passed stop line
MOTORBIKE_COUNT = set()  # Track motorbikes (xe máy)
CAR_COUNT = set()  # Track cars/trucks/buses (ô tô, xe tải, xe bus)
VEHICLE_CLASSES = {0: "o to", 1: "xe bus", 2: "xe dap", 3: "xe may", 4: "xe tai", 5: "bien so xe"}  # Custom model classes
ALLOWED_VEHICLE_IDS = [0, 1, 2, 3, 4, 5]

def is_on_stop_line(cx, cy, threshold=15):
    """Check if point is on THE stopline"""
    global STOP_LINE
    if STOP_LINE is None:
        return False
    p1, p2 = STOP_LINE
    dist = point_to_segment_distance(cx, cy, p1[0], p1[1], p2[0], p2[1])
    return dist < threshold

# NOTE: calculate_vehicle_direction and estimate_vehicle_speed are imported from app.detection
# They use VEHICLE_POSITIONS via set_vehicle_positions_ref() called above

# NOTE: check_speed_violation is imported from app.detection (100% identical)

# NOTE: check_lane_direction_match and check_tl_violation are imported from app.detection
# They use TL_ROIS, DIRECTION_ROIS, VEHICLE_DIRECTIONS via set_violation_checker_globals() called in __init__


class MainWindow(QMainWindow, DirectionROIHandlerMixin, ReferenceVectorHandlerMixin, TrafficLightHandlerMixin, LaneHandlerMixin, ConfigHandlerMixin, EventHandlerMixin, ModelHandlerMixin, DisplayHandlerMixin, DialogHandlerMixin, VideoHandlerMixin, DetectionHandlerMixin):
    def __init__(self):
        super().__init__()
        
        # Declare globals used in this method
        global VIOLATOR_TRACK_IDS, RED_LIGHT_VIOLATORS, LANE_VIOLATORS, PASSED_VEHICLES, MOTORBIKE_COUNT, CAR_COUNT
        global ALLOWED_VEHICLE_IDS, VEHICLE_CLASSES, LANE_CONFIGS, TL_ROIS, _show_all_boxes
        global DIRECTION_ROIS, _tmp_direction_roi_pts, _selected_direction
        
        # ⚠️ CRITICAL: Link globals to violation_checker module HERE (in __init__)
        # This ensures proper module context - same lists as used by this MainWindow instance
        set_violation_checker_globals(TL_ROIS, DIRECTION_ROIS, VEHICLE_DIRECTIONS)
        print(f"✅ [MainWindow.__init__] Linked globals: TL_ROIS id={id(TL_ROIS)}")
        
        # Initialize ROI Editor
        self.roi_editor = ROIEditor()
        
        # Ask user to select video FIRST before showing main UI
        video_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File to Start",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)"
        )
        
        if not video_path:
            # User cancelled - exit application
            print("❌ No video selected. Exiting...")
            QApplication.quit()
            return
        
        self.video_path = video_path
        print(f"📹 Selected video: {video_path}")
        
        # Now setup the UI
        self.setWindowTitle("Traffic Violation Detector - Integrated")
        self.setGeometry(50, 50, 1600, 900)
        
        # Pre-load YOLO model in main thread to avoid DLL issues in QThread
        self.yolo_model = None
        self.current_model_type = None
        self.current_model_config = None
        self.device = 'cuda:0' if CUDA_AVAILABLE else 'cpu'  # Default device
        print(f"📦 Default device: {self.device}")
        
        # Try to migrate old weights first
        migrate_old_weights()
        
        # Scan available models
        self.available_models = scan_all_models()
        print(f"📦 Available models: {list(self.available_models.keys())}")
        
        # Setup menu bar AFTER available_models is initialized
        self.setup_menu_bar()
        
        # Auto-load first available model
        if YOLO_AVAILABLE and self.available_models:
            first_model_type = list(self.available_models.keys())[0]
            first_weight = self.available_models[first_model_type]["weights"][0]
            self.load_model(first_model_type, first_weight)
        else:
            print("⚠️ YOLO not available or no models found, detection disabled")
        
        # Initialize TL tracking (manual ROI only, no auto-detection)
        self.tl_tracking_active = False  # Continuous color tracking flag
        self.tl_color_frame_count = 0  # Counter for color update throttling
        self.tl_force_update_on_next_frame = False  # Force immediate color update flag
        self.cap = None  # Will be set when video loads
        print("✅ Manual TL ROI mode enabled")
        
        # Initialize display scale variables for accurate click detection
        self.current_display_scale = 1.0
        self.current_display_width = 1024
        self.current_display_height = 768
        self.current_display_offset_x = 0
        self.current_display_offset_y = 0

        # Playback UI state
        self.video_zoom_factor = 1.0
        self.video_zoom_step = 0.25
        self.video_min_zoom = 1.0
        self.video_max_zoom = 4.0
        self.video_pan_x = 0.0
        self.video_pan_y = 0.0
        self.is_panning_video = False
        self._last_pan_mouse_pos = None
        self._timeline_user_dragging = False
        self._playback_duration_sec = 0.0
        
        # Main layout
        main_layout = QHBoxLayout()
        
        # Left side - Video display
        self.video_label = QLabel()
        self.video_label.setScaledContents(False)
        self.video_label.setAlignment(Qt.AlignCenter)  # Center the pixmap to match offset calculation
        self.video_label.setMinimumSize(1024, 768)
        self.video_label.mousePressEvent = self.video_mouse_press
        self.video_label.mouseMoveEvent = self.video_mouse_move
        self.video_label.mouseReleaseEvent = self.video_mouse_release
        self.video_label.mouseDoubleClickEvent = self.video_mouse_double_click
        
        # Enable context menu on video label
        self.video_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_label.customContextMenuRequested.connect(self.show_context_menu)
        
        main_layout.addWidget(self.video_label)

        # Playback controls (always visible under the video)
        playback_layout = QHBoxLayout()
        playback_layout.addWidget(QLabel("Playback:"))

        self.btn_seek_back_5s = QPushButton("-5s")
        self.btn_seek_back_5s.clicked.connect(self.seek_backward_5s)
        playback_layout.addWidget(self.btn_seek_back_5s)

        self.btn_pause_playback = QPushButton("Pause")
        self.btn_pause_playback.clicked.connect(self.toggle_play_pause)
        playback_layout.addWidget(self.btn_pause_playback)

        self.btn_seek_forward_5s = QPushButton("+5s")
        self.btn_seek_forward_5s.clicked.connect(self.seek_forward_5s)
        playback_layout.addWidget(self.btn_seek_forward_5s)

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.sliderPressed.connect(self._on_timeline_slider_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_timeline_slider_released)
        playback_layout.addWidget(self.timeline_slider, 1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(120)
        playback_layout.addWidget(self.time_label)

        self.btn_zoom_out = QPushButton("Zoom -")
        self.btn_zoom_out.clicked.connect(self.zoom_out_video)
        playback_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("1x")
        self.btn_zoom_reset.clicked.connect(self.reset_video_zoom)
        playback_layout.addWidget(self.btn_zoom_reset)

        self.btn_zoom_in = QPushButton("Zoom +")
        self.btn_zoom_in.clicked.connect(self.zoom_in_video)
        playback_layout.addWidget(self.btn_zoom_in)

        self.zoom_label = QLabel("1.00x")
        self.zoom_label.setMinimumWidth(52)
        playback_layout.addWidget(self.zoom_label)
        
        # Right side - Control panel
        control_layout = QVBoxLayout()
        
        # Model selection
        control_layout.addWidget(QLabel("Model Selection"))
        
        self.model_type_combo = QComboBox()
        for model_type, info in self.available_models.items():
            self.model_type_combo.addItem(f"{model_type} - {info['config']['description']}")
        self.model_type_combo.currentIndexChanged.connect(self.on_model_type_changed)
        control_layout.addWidget(self.model_type_combo)
        
        self.weight_combo = QComboBox()
        self.update_weight_combo()
        self.weight_combo.currentIndexChanged.connect(self.on_weight_changed)
        control_layout.addWidget(self.weight_combo)
        
        self.model_info_label = QLabel("")
        self.update_model_info_label()
        control_layout.addWidget(self.model_info_label)
        
        # Model parameters
        control_layout.addWidget(QLabel("Detection Parameters"))
        
        # Image size control
        imgsz_layout = QHBoxLayout()
        imgsz_layout.addWidget(QLabel("ImgSize:"))
        self.imgsz_spinbox = QSpinBox()
        self.imgsz_spinbox.setMinimum(320)
        self.imgsz_spinbox.setMaximum(1280)
        self.imgsz_spinbox.setSingleStep(32)
        self.imgsz_spinbox.setValue(416 if self.current_model_config else 416)
        self.imgsz_spinbox.valueChanged.connect(self.on_imgsz_changed)
        imgsz_layout.addWidget(self.imgsz_spinbox)
        control_layout.addLayout(imgsz_layout)
        
        # Confidence threshold control
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        self.conf_spinbox = QDoubleSpinBox()
        self.conf_spinbox.setMinimum(0.1)
        self.conf_spinbox.setMaximum(0.95)
        self.conf_spinbox.setSingleStep(0.05)
        self.conf_spinbox.setDecimals(2)
        self.conf_spinbox.setValue(0.3 if self.current_model_config else 0.3)
        self.conf_spinbox.valueChanged.connect(self.on_conf_changed)
        conf_layout.addWidget(self.conf_spinbox)
        control_layout.addLayout(conf_layout)
        
        # Lane management
        control_layout.addWidget(QLabel("Lane Management"))
        self.lane_list = QListWidget()
        control_layout.addWidget(self.lane_list)
        
        self.btn_add_lane = QPushButton("Add Lane (Click on video)")
        self.btn_add_lane.clicked.connect(self.start_add_lane)
        control_layout.addWidget(self.btn_add_lane)
        
        self.btn_delete_lane = QPushButton("Delete Selected Lane")
        self.btn_delete_lane.clicked.connect(self.delete_lane)
        control_layout.addWidget(self.btn_delete_lane)
        
        # Stop line management
        control_layout.addWidget(QLabel("Stop Line (Single)"))
        
        self.btn_add_stopline = QPushButton("Set Stop Line (Click 2 points)")
        self.btn_add_stopline.clicked.connect(self.start_add_stopline)
        control_layout.addWidget(self.btn_add_stopline)
        
        self.btn_delete_stopline = QPushButton("Delete Stop Line")
        self.btn_delete_stopline.clicked.connect(self.delete_stopline)
        control_layout.addWidget(self.btn_delete_stopline)
        
        # Start detection
        self.btn_start = QPushButton("Start Detection")
        self.btn_start.clicked.connect(self.start_detection)
        control_layout.addWidget(self.btn_start)
        
        # Toggle bounding box display
        self.btn_toggle_bb = QPushButton("Show All Boxes: ON")
        self.btn_toggle_bb.setCheckable(True)
        self.btn_toggle_bb.setChecked(True)
        self.btn_toggle_bb.clicked.connect(self.toggle_bbox_display)
        control_layout.addWidget(self.btn_toggle_bb)
        
        # Toggle violator trajectory display
        self.btn_toggle_trajectory = QPushButton("Violator Trajectory: ON")
        self.btn_toggle_trajectory.setCheckable(True)
        self.btn_toggle_trajectory.setChecked(True)
        self.btn_toggle_trajectory.clicked.connect(self.toggle_trajectory_display)
        control_layout.addWidget(self.btn_toggle_trajectory)
        
        # Select video button
        self.btn_select_video = QPushButton("Select Video File")
        self.btn_select_video.clicked.connect(self.select_video)
        control_layout.addWidget(self.btn_select_video)

        # Traffic light tools
        self.btn_find_tl = QPushButton("Add Traffic Light (Draw ROI)")
        self.btn_find_tl.clicked.connect(self.find_tl_roi)
        control_layout.addWidget(self.btn_find_tl)
        
        self.btn_delete_tl = QPushButton("Delete Traffic Light")
        self.btn_delete_tl.clicked.connect(self.delete_tl)
        control_layout.addWidget(self.btn_delete_tl)
        
        # Direction Detection tools
        control_layout.addWidget(QLabel("Direction ROI Management"))
        
        # Direction selector (dropdown instead of keyboard)
        dir_select_layout = QHBoxLayout()
        dir_select_layout.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["left", "straight", "right"])
        self.direction_combo.setCurrentText("straight")
        self.direction_combo.currentTextChanged.connect(self.on_direction_changed)
        dir_select_layout.addWidget(self.direction_combo)
        control_layout.addLayout(dir_select_layout)
        
        self.btn_add_direction_roi = QPushButton("Draw Direction ROI (Click points)")
        self.btn_add_direction_roi.clicked.connect(self.start_add_direction_roi)
        control_layout.addWidget(self.btn_add_direction_roi)
        
        self.btn_finish_direction_roi = QPushButton("Finish Direction ROI")
        self.btn_finish_direction_roi.clicked.connect(self.finish_direction_roi)
        self.btn_finish_direction_roi.setEnabled(False)
        control_layout.addWidget(self.btn_finish_direction_roi)
        
        self.direction_roi_list = QListWidget()
        control_layout.addWidget(self.direction_roi_list)
        
        self.btn_delete_direction_roi = QPushButton("Delete Selected Direction ROI")
        self.btn_delete_direction_roi.clicked.connect(self.delete_direction_roi)
        control_layout.addWidget(self.btn_delete_direction_roi)
        
        # Edit Direction ROI tool
        self.btn_edit_direction_roi = QPushButton("Edit Selected Direction ROI")
        self.btn_edit_direction_roi.clicked.connect(self.start_edit_direction_roi)
        control_layout.addWidget(self.btn_edit_direction_roi)
        
        self.btn_finish_edit_roi = QPushButton("Finish Editing")
        self.btn_finish_edit_roi.clicked.connect(self._finish_current_editing)
        self.btn_finish_edit_roi.setEnabled(False)
        control_layout.addWidget(self.btn_finish_edit_roi)
        
        self.btn_smooth_roi = QPushButton("Smooth ROI (reduce points)")
        self.btn_smooth_roi.clicked.connect(self.smooth_current_roi)
        self.btn_smooth_roi.setEnabled(False)
        control_layout.addWidget(self.btn_smooth_roi)
        
        self.btn_change_roi_direction = QPushButton("Change ROI Directions")
        self.btn_change_roi_direction.clicked.connect(self.change_roi_directions)
        self.btn_change_roi_direction.setEnabled(False)
        control_layout.addWidget(self.btn_change_roi_direction)
        
        # Toggle show direction ROIs
        self.btn_toggle_direction_rois = QPushButton("Show Direction ROIs: ON")
        self.btn_toggle_direction_rois.setCheckable(True)
        self.btn_toggle_direction_rois.setChecked(True)
        self.btn_toggle_direction_rois.clicked.connect(self.toggle_direction_rois)
        control_layout.addWidget(self.btn_toggle_direction_rois)
        
        # Reference Vector (for camera nghiêng)
        control_layout.addWidget(QLabel("Reference Vector (Camera Tilted)"))
        
        self.btn_set_ref_vector = QPushButton("Set Reference Vector (2 points)")
        self.btn_set_ref_vector.clicked.connect(self.start_set_reference_vector)
        control_layout.addWidget(self.btn_set_ref_vector)
        
        self.btn_finish_ref_vector = QPushButton("Finish Reference Vector")
        self.btn_finish_ref_vector.clicked.connect(self.finish_reference_vector)
        self.btn_finish_ref_vector.setEnabled(False)
        control_layout.addWidget(self.btn_finish_ref_vector)
        
        self.ref_vector_label = QLabel("⚠️ Ref Vector: Not set - Required for turn detection!")
        self.ref_vector_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
        self.ref_vector_label.setWordWrap(True)
        control_layout.addWidget(self.ref_vector_label)
        
        # Add helpful hint
        ref_vector_hint = QLabel("💡 Hint: Click 2 points on a STRAIGHT lane\n(from start to end in traffic flow direction)")
        ref_vector_hint.setStyleSheet("QLabel { color: gray; font-size: 9pt; font-style: italic; }")
        ref_vector_hint.setWordWrap(True)
        control_layout.addWidget(ref_vector_hint)
        
        self.show_direction_rois = True
        self.show_lanes = True  # Toggle for lane display
        self.show_roi_overlays = True  # Toggle for ROI overlay display
        self.show_stopline = True  # Toggle for stopline display
        self.show_traffic_lights = True  # Toggle for traffic lights display
        self.show_ref_vector = True  # Toggle for reference vector display
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        
        # Config Manager
        self.config_manager = ConfigManager()
        
        # Save/Load Configuration buttons
        control_layout.addWidget(QLabel("Configuration Management"))
        
        self.btn_save_config = QPushButton("💾 Save All ROIs Configuration")
        self.btn_save_config.clicked.connect(self.save_configuration)
        self.btn_save_config.setStyleSheet("QPushButton { font-weight: bold; background-color: #4CAF50; color: white; }")
        control_layout.addWidget(self.btn_save_config)
        
        self.btn_load_config = QPushButton("📂 Load Configuration")
        self.btn_load_config.clicked.connect(self.load_configuration)
        control_layout.addWidget(self.btn_load_config)
        
        self.config_status_label = QLabel("Config: Not loaded")
        self.config_status_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        control_layout.addWidget(self.config_status_label)
        
        self.status_label = QLabel("Status: Ready - Direction-based detection")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # Hide control panel - all controls moved to menu bar
        # main_layout.addLayout(control_layout)  # COMMENTED OUT
        
        # Add status bar instead
        self.statusBar().showMessage("Ready - Direction-based detection")
        
        # Create central widget and set layout (video + playback controls)
        root_layout = QVBoxLayout()
        root_layout.addLayout(main_layout)
        root_layout.addLayout(playback_layout)

        central_widget = QWidget()
        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)
        
        # Store control_layout reference for future use if needed
        self.control_layout = control_layout
        self.control_panel_visible = False
        
        # Video thread - start with selected video
        self.thread = VideoThread(self.video_path)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.error_signal.connect(self.show_error)
        self.thread.playback_info_signal.connect(self.update_playback_info)
        
        # Pass globals reference to thread
        # Use lambda for _show_all_boxes to get real-time value
        self.thread.set_globals_reference({
            'ALLOWED_VEHICLE_IDS': ALLOWED_VEHICLE_IDS,
            'VEHICLE_CLASSES': VEHICLE_CLASSES,
            'LANE_CONFIGS': LANE_CONFIGS,
            'TL_ROIS': TL_ROIS,
            'DIRECTION_ROIS': DIRECTION_ROIS,
            'get_show_all_boxes': lambda: globals()['_show_all_boxes'],
            'is_on_stop_line': is_on_stop_line,
            'check_tl_violation': check_tl_violation,
            'point_in_polygon': point_in_polygon,
            'VIOLATOR_TRACK_IDS': VIOLATOR_TRACK_IDS,
            'RED_LIGHT_VIOLATORS': RED_LIGHT_VIOLATORS,
            'LANE_VIOLATORS': LANE_VIOLATORS,
            'DIRECTION_VIOLATORS': DIRECTION_VIOLATORS,
            'PASSED_VEHICLES': PASSED_VEHICLES,
            'MOTORBIKE_COUNT': MOTORBIKE_COUNT,
            'CAR_COUNT': CAR_COUNT
        })
        
        # Set model and config to thread if loaded
        if self.yolo_model is not None:
            self.thread.set_model(self.yolo_model)
            self.thread.model_config = self.current_model_config
        
        self.thread.start()
        
        # Initialize cap and current_frame for TL detection
        self.current_frame = None
        self.cap = cv2.VideoCapture(self.video_path)
        
        # Wait for first frame before auto-detect
        import time
        time.sleep(0.5)  # Wait for video thread to emit first frame
        
        # Trigger auto-detect after first frame is ready
        if self.cap.isOpened():
            ret, first_frame = self.cap.read()
            if ret:
                self.current_frame = first_frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start
        
        # ⚠️ CRITICAL FIX: Auto-load configuration for initial video (same as select_video)
        # This ensures violation detection works immediately after starting, not only after switching videos
        if self.config_manager.config_exists(self.video_path):
            print(f"🔍 Found existing configuration for initial video")
            if self.auto_load_configuration():
                self.config_status_label.setText(f"✅ Config: Auto-loaded from file")
                self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                self.status_label.setText(f"Status: Loaded video [Config auto-loaded]")
                print("✅ Configuration auto-loaded for initial video - Violation detection ready!")
            else:
                print("⚠️ Failed to auto-load configuration for initial video")
        else:
            print("ℹ️ No saved configuration found for initial video - Draw ROIs manually")
        
        self.update_lists()
        self.reset_playback_ui_for_new_video()
    
    # NOTE: update_image moved to DisplayHandlerMixin
    # NOTE: draw_direction_rois moved to DisplayHandlerMixin
    
    def setup_menu_bar(self):
        """Setup menu bar with organized menus"""
        menubar = self.menuBar()
        
        # === FILE Menu ===
        file_menu = menubar.addMenu("📁 &File")
        
        # Select video
        action_select_video = QAction("Open Video...", self)
        action_select_video.setShortcut("Ctrl+O")
        action_select_video.triggered.connect(self.select_video)
        file_menu.addAction(action_select_video)
        
        file_menu.addSeparator()
        
        # Save/Load config
        action_save_config = QAction("💾 Save Configuration", self)
        action_save_config.setShortcut("Ctrl+S")
        action_save_config.triggered.connect(self.save_configuration)
        file_menu.addAction(action_save_config)
        
        action_load_config = QAction("📂 Load Configuration", self)
        action_load_config.setShortcut("Ctrl+L")
        action_load_config.triggered.connect(self.load_configuration)
        file_menu.addAction(action_load_config)
        
        file_menu.addSeparator()
        
        # Exit
        action_exit = QAction("Exit", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)
        
        # === DRAW Menu ===
        draw_menu = menubar.addMenu("🎨 &Draw")
        
        # Lane
        action_add_lane = QAction("Add Lane (Polygon)", self)
        action_add_lane.setShortcut("L")
        action_add_lane.triggered.connect(self.start_add_lane)
        draw_menu.addAction(action_add_lane)
        
        # Stopline
        action_add_stopline = QAction("Set Stop Line", self)
        action_add_stopline.setShortcut("S")
        action_add_stopline.triggered.connect(self.start_add_stopline)
        draw_menu.addAction(action_add_stopline)
        
        # Traffic light
        action_add_tl = QAction("Add Traffic Light", self)
        action_add_tl.setShortcut("T")
        action_add_tl.triggered.connect(self.find_tl_roi)
        draw_menu.addAction(action_add_tl)
        
        # Direction ROI
        action_add_direction = QAction("Draw Direction ROI", self)
        action_add_direction.setShortcut("D")
        action_add_direction.triggered.connect(self.start_add_direction_roi)
        draw_menu.addAction(action_add_direction)
        
        draw_menu.addSeparator()
        
        # Reference vector
        action_ref_vector = QAction("Set Reference Vector", self)
        action_ref_vector.setShortcut("R")
        action_ref_vector.triggered.connect(self.start_set_reference_vector)
        draw_menu.addAction(action_ref_vector)
        
        # === EDIT Menu ===
        edit_menu = menubar.addMenu("✏️ &Edit")
        
        # Edit Lane (drag points + vehicle types)
        self.action_edit_lane = QAction("Edit Lane...", self)
        self.action_edit_lane.triggered.connect(self.start_edit_lane)
        edit_menu.addAction(self.action_edit_lane)

        # Edit direction ROI
        self.action_edit_direction = QAction("Edit Direction ROI...", self)
        self.action_edit_direction.setShortcut("E")
        self.action_edit_direction.triggered.connect(self.show_edit_roi_dialog)
        edit_menu.addAction(self.action_edit_direction)

        edit_menu.addSeparator()

        # Smooth ROI
        self.action_smooth_roi = QAction("Smooth ROI", self)
        self.action_smooth_roi.triggered.connect(self.smooth_current_roi)
        self.action_smooth_roi.setEnabled(False)
        edit_menu.addAction(self.action_smooth_roi)
        
        # Change directions
        self.action_change_directions = QAction("Change ROI Directions", self)
        self.action_change_directions.triggered.connect(self.change_roi_directions)
        self.action_change_directions.setEnabled(False)
        edit_menu.addAction(self.action_change_directions)
        
        edit_menu.addSeparator()
        
        # Finish editing
        self.action_finish_edit = QAction("Finish Editing", self)
        # Note: No shortcut to avoid conflict with dialog buttons
        self.action_finish_edit.triggered.connect(self._finish_current_editing)
        self.action_finish_edit.setEnabled(False)
        edit_menu.addAction(self.action_finish_edit)
        
        # === DELETE Menu ===
        delete_menu = menubar.addMenu("🗑️ De&lete")
        
        action_delete_lane = QAction("Delete Selected Lane", self)
        action_delete_lane.setShortcut("Delete")
        action_delete_lane.triggered.connect(self.delete_lane)
        delete_menu.addAction(action_delete_lane)
        
        action_delete_stopline = QAction("Delete Stop Line", self)
        action_delete_stopline.triggered.connect(self.delete_stopline)
        delete_menu.addAction(action_delete_stopline)
        
        action_delete_tl = QAction("Delete Traffic Light", self)
        action_delete_tl.triggered.connect(self.delete_tl)
        delete_menu.addAction(action_delete_tl)
        
        action_delete_direction = QAction("Delete Direction ROI", self)
        action_delete_direction.triggered.connect(self.delete_direction_roi)
        delete_menu.addAction(action_delete_direction)
        
        # === VIEW Menu ===
        view_menu = menubar.addMenu("👁️ &View")
        
        # Toggle lanes
        self.action_toggle_lanes = QAction("Show Lanes", self)
        self.action_toggle_lanes.setCheckable(True)
        self.action_toggle_lanes.setChecked(True)
        self.action_toggle_lanes.triggered.connect(self.toggle_lane_display)
        view_menu.addAction(self.action_toggle_lanes)

        # Toggle stopline
        self.action_toggle_stopline = QAction("Show Stop Line", self)
        self.action_toggle_stopline.setCheckable(True)
        self.action_toggle_stopline.setChecked(True)
        self.action_toggle_stopline.triggered.connect(self.toggle_stopline_display)
        view_menu.addAction(self.action_toggle_stopline)

        # Toggle traffic lights
        self.action_toggle_traffic_lights = QAction("Show Traffic Lights", self)
        self.action_toggle_traffic_lights.setCheckable(True)
        self.action_toggle_traffic_lights.setChecked(True)
        self.action_toggle_traffic_lights.triggered.connect(self.toggle_traffic_lights_display)
        view_menu.addAction(self.action_toggle_traffic_lights)

        # Toggle direction ROIs
        self.action_toggle_rois = QAction("Show Direction ROIs", self)
        self.action_toggle_rois.setCheckable(True)
        self.action_toggle_rois.setChecked(True)
        self.action_toggle_rois.triggered.connect(self.toggle_roi_display)
        view_menu.addAction(self.action_toggle_rois)

        # Toggle reference vector
        self.action_toggle_ref_vector = QAction("Show Reference Vector", self)
        self.action_toggle_ref_vector.setCheckable(True)
        self.action_toggle_ref_vector.setChecked(True)
        self.action_toggle_ref_vector.triggered.connect(self.toggle_ref_vector_display)
        view_menu.addAction(self.action_toggle_ref_vector)

        view_menu.addSeparator()

        # Toggle all boxes
        self.action_toggle_boxes = QAction("Show All Bounding Boxes", self)
        self.action_toggle_boxes.setCheckable(True)
        self.action_toggle_boxes.setChecked(True)
        self.action_toggle_boxes.triggered.connect(self.toggle_bbox_display)
        view_menu.addAction(self.action_toggle_boxes)
        
        # === SETTINGS Menu ===
        settings_menu = menubar.addMenu("⚙️ &Settings")
        
        # Model selection submenu with weights
        model_menu = settings_menu.addMenu("🤖 Model Selection")
        
        # Create submenu for each model type with all weights
        self.model_type_actions = []
        for model_type, info in self.available_models.items():
            # Create submenu for this model type
            type_menu = model_menu.addMenu(f"{model_type} - {info['config']['description']}")
            
            # Add action for each weight file
            for weight in info['weights']:
                weight_action = QAction(weight, self)
                weight_action.triggered.connect(
                    lambda checked, mt=model_type, wt=weight: self.load_model(mt, wt)
                )
                type_menu.addAction(weight_action)
            
            self.model_type_actions.append(type_menu)
        
        settings_menu.addSeparator()
        
        # Detection parameters submenu
        params_menu = settings_menu.addMenu("📊 Detection Parameters")
        
        # Add image size action
        action_imgsz = QAction("Set Image Size...", self)
        action_imgsz.triggered.connect(self.show_imgsz_dialog)
        params_menu.addAction(action_imgsz)
        
        # Add confidence action
        action_conf = QAction("Set Confidence Threshold...", self)
        action_conf.triggered.connect(self.show_conf_dialog)
        params_menu.addAction(action_conf)
        
        settings_menu.addSeparator()
        
        # License plate tracking mode
        plate_menu = settings_menu.addMenu("🎫 License Plate Tracking")
        
        self.action_plate_yolo_direct = QAction("YOLO Direct Detection (Default)", self)
        self.action_plate_yolo_direct.setCheckable(True)
        self.action_plate_yolo_direct.setChecked(True)
        self.action_plate_yolo_direct.triggered.connect(self.set_plate_mode_yolo)
        plate_menu.addAction(self.action_plate_yolo_direct)
        
        self.action_plate_relative = QAction("Relative Position Tracking", self)
        self.action_plate_relative.setCheckable(True)
        self.action_plate_relative.setChecked(False)
        self.action_plate_relative.triggered.connect(self.set_plate_mode_relative)
        plate_menu.addAction(self.action_plate_relative)
        
        plate_menu.addSeparator()
        
        # Info text
        action_plate_info = QAction("💡 YOLO: Let model detect plates directly", self)
        action_plate_info.setEnabled(False)
        plate_menu.addAction(action_plate_info)
        
        action_plate_info2 = QAction("💡 Relative: Track plate position within vehicle", self)
        action_plate_info2.setEnabled(False)
        plate_menu.addAction(action_plate_info2)
        
        settings_menu.addSeparator()
        
        # OCR toggle
        self.action_toggle_ocr = QAction("🔤 Enable OCR (License Plate Text Recognition)", self)
        self.action_toggle_ocr.setCheckable(True)
        self.action_toggle_ocr.setChecked(True)  # Default ON
        self.action_toggle_ocr.triggered.connect(self.toggle_ocr)
        settings_menu.addAction(self.action_toggle_ocr)
        
        settings_menu.addSeparator()
        
        # Device selection (GPU/CPU)
        device_menu = settings_menu.addMenu("💻 Device Selection")
        
        self.action_device_gpu = QAction("🚀 GPU (CUDA)", self)
        self.action_device_gpu.setCheckable(True)
        self.action_device_gpu.setEnabled(CUDA_AVAILABLE)  # Only enable if CUDA available
        self.action_device_gpu.setChecked(CUDA_AVAILABLE)  # Default to GPU if available
        self.action_device_gpu.triggered.connect(self.set_device_gpu)
        device_menu.addAction(self.action_device_gpu)
        
        self.action_device_cpu = QAction("🐌 CPU", self)
        self.action_device_cpu.setCheckable(True)
        self.action_device_cpu.setChecked(not CUDA_AVAILABLE)  # Default to CPU if no CUDA
        self.action_device_cpu.triggered.connect(self.set_device_cpu)
        device_menu.addAction(self.action_device_cpu)
        
        device_menu.addSeparator()
        
        # Info text
        if CUDA_AVAILABLE:
            gpu_name = torch.cuda.get_device_name(0)
            action_device_info = QAction(f"💡 Available: {gpu_name}", self)
        else:
            action_device_info = QAction("⚠️ No CUDA-capable GPU detected", self)
        action_device_info.setEnabled(False)
        device_menu.addAction(action_device_info)

        # === PLAYBACK Menu ===
        playback_menu = menubar.addMenu("▶️ &Playback")

        self.action_toggle_playback = QAction("Pause", self)
        self.action_toggle_playback.setShortcut("K")
        self.action_toggle_playback.triggered.connect(self.toggle_play_pause)
        playback_menu.addAction(self.action_toggle_playback)

        self.action_seek_back_5s = QAction("Seek -5s", self)
        self.action_seek_back_5s.setShortcut("Ctrl+Left")
        self.action_seek_back_5s.triggered.connect(self.seek_backward_5s)
        playback_menu.addAction(self.action_seek_back_5s)

        self.action_seek_forward_5s = QAction("Seek +5s", self)
        self.action_seek_forward_5s.setShortcut("Ctrl+Right")
        self.action_seek_forward_5s.triggered.connect(self.seek_forward_5s)
        playback_menu.addAction(self.action_seek_forward_5s)

        playback_menu.addSeparator()

        self.action_zoom_in = QAction("Zoom In", self)
        self.action_zoom_in.setShortcut("Ctrl++")
        self.action_zoom_in.triggered.connect(self.zoom_in_video)
        playback_menu.addAction(self.action_zoom_in)

        self.action_zoom_out = QAction("Zoom Out", self)
        self.action_zoom_out.setShortcut("Ctrl+-")
        self.action_zoom_out.triggered.connect(self.zoom_out_video)
        playback_menu.addAction(self.action_zoom_out)

        self.action_zoom_reset = QAction("Reset Zoom", self)
        self.action_zoom_reset.setShortcut("Ctrl+0")
        self.action_zoom_reset.triggered.connect(self.reset_video_zoom)
        playback_menu.addAction(self.action_zoom_reset)

        
        # === DETECTION Menu ===
        detection_menu = menubar.addMenu("🚀 &Detection")
        
        self.action_start_detection = QAction("Start Detection", self)
        self.action_start_detection.setShortcut("Space")
        self.action_start_detection.triggered.connect(self.start_detection)
        detection_menu.addAction(self.action_start_detection)
        
        # === HELP Menu ===
        help_menu = menubar.addMenu("❓ &Help")
        
        action_about = QAction("About", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)
        
        action_shortcuts = QAction("Keyboard Shortcuts", self)
        action_shortcuts.setShortcut("F1")
        action_shortcuts.triggered.connect(self.show_shortcuts)
        help_menu.addAction(action_shortcuts)
    
    # NOTE: show_about moved to DialogHandlerMixin
    # NOTE: show_shortcuts moved to DialogHandlerMixin
    # NOTE: show_imgsz_dialog moved to DialogHandlerMixin
    # NOTE: show_conf_dialog moved to DialogHandlerMixin
    # NOTE: show_lane_list_dialog moved to DialogHandlerMixin
    # NOTE: show_direction_list_dialog moved to DialogHandlerMixin
    # NOTE: toggle_lane_display moved to DisplayHandlerMixin
    # NOTE: toggle_roi_display moved to DisplayHandlerMixin
    # NOTE: show_edit_roi_dialog moved to DetectionHandlerMixin
    # NOTE: start_edit_selected_roi moved to DetectionHandlerMixin
    # NOTE: delete_selected_roi moved to DetectionHandlerMixin
    # NOTE: update_lists moved to DetectionHandlerMixin
    # NOTE: start_detection moved to DetectionHandlerMixin
    # NOTE: toggle_bbox_display moved to DisplayHandlerMixin
    # NOTE: select_video moved to VideoHandlerMixin
    # NOTE: show_error moved to VideoHandlerMixin
    
    def set_plate_mode_yolo(self):
        """Set license plate tracking mode to YOLO direct detection"""
        self.action_plate_yolo_direct.setChecked(True)
        self.action_plate_relative.setChecked(False)
        
        if hasattr(self, 'thread') and self.thread:
            self.thread.use_plate_relative_tracking = False
            print("🔹 License Plate Mode: YOLO Direct Detection")
        
        self.statusBar().showMessage("License Plate: YOLO Direct Detection", 3000)
    
    def set_plate_mode_relative(self):
        """Set license plate tracking mode to relative position tracking"""
        self.action_plate_yolo_direct.setChecked(False)
        self.action_plate_relative.setChecked(True)
        
        if hasattr(self, 'thread') and self.thread:
            self.thread.use_plate_relative_tracking = True
            print("🟠 License Plate Mode: Relative Position Tracking")
        
        self.statusBar().showMessage("License Plate: Relative Position Tracking", 3000)    
    def toggle_ocr(self):
        """Toggle OCR (License Plate Text Recognition) on/off"""
        is_enabled = self.action_toggle_ocr.isChecked()
        
        if hasattr(self, 'thread') and self.thread:
            self.thread.enable_ocr = is_enabled
            
            if is_enabled:
                print("✅ OCR Enabled: License plate text will be recognized")
                self.statusBar().showMessage("OCR: Enabled ✅", 3000)
                self.action_toggle_ocr.setText("🔤 Disable OCR (License Plate Text Recognition)")
            else:
                print("⏸️ OCR Disabled: License plate text recognition turned off")
                self.statusBar().showMessage("OCR: Disabled ⏸️", 3000)
                self.action_toggle_ocr.setText("🔤 Enable OCR (License Plate Text Recognition)")    
    def set_device_gpu(self):
        """Set device to GPU (CUDA)"""
        if not CUDA_AVAILABLE:
            QMessageBox.warning(self, "GPU Not Available", 
                              "CUDA-capable GPU not detected!\nPlease install CUDA and compatible PyTorch.")
            return
        
        self.action_device_gpu.setChecked(True)
        self.action_device_cpu.setChecked(False)
        self.device = 'cuda:0'
        print(f"🚀 Device set to: GPU (CUDA) - {torch.cuda.get_device_name(0)}")
        
        # Reload model on new device if already loaded
        if self.yolo_model is not None:
            self.yolo_model.to(self.device)
            if hasattr(self, 'thread') and self.thread:
                self.thread.set_model(self.yolo_model)
            print(f"✅ Model moved to {self.device}")
        
        self.statusBar().showMessage(f"Device: GPU ({torch.cuda.get_device_name(0)})", 3000)
    
    def set_device_cpu(self):
        """Set device to CPU"""
        self.action_device_gpu.setChecked(False)
        self.action_device_cpu.setChecked(True)
        self.device = 'cpu'
        print("🐌 Device set to: CPU")
        
        # Reload model on new device if already loaded
        if self.yolo_model is not None:
            self.yolo_model.to(self.device)
            if hasattr(self, 'thread') and self.thread:
                self.thread.set_model(self.yolo_model)
            print(f"✅ Model moved to {self.device}")
        
        self.statusBar().showMessage("Device: CPU", 3000)
    
    def _finish_current_editing(self):
        """Finish current editing - calls appropriate finish method based on what's being edited"""
        if hasattr(self, 'roi_editor'):
            print(f"🔍 _finish_current_editing: is_editing={self.roi_editor.is_editing()}, "
                  f"is_editing_lane={self.roi_editor.is_editing_lane()}, "
                  f"is_editing_direction={self.roi_editor.is_editing_direction()}, "
                  f"editing_type={self.roi_editor.editing_type}")
            if self.roi_editor.is_editing_lane():
                print("📌 Calling finish_edit_lane()")
                self.finish_edit_lane()
            elif self.roi_editor.is_editing_direction():
                print("📌 Calling finish_edit_roi()")
                self.finish_edit_roi()
            else:
                print("⚠️ Not editing anything")

    @staticmethod
    def _format_time_seconds(total_seconds):
        """Format seconds as HH:MM:SS or MM:SS."""
        sec = max(0, int(round(float(total_seconds))))
        hours = sec // 3600
        minutes = (sec % 3600) // 60
        seconds = sec % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def reset_playback_ui_for_new_video(self):
        """Reset playback widgets when opening a new video."""
        self._timeline_user_dragging = False
        self._playback_duration_sec = 0.0
        self.current_frame = None
        self.video_pan_x = 0.0
        self.video_pan_y = 0.0
        self.is_panning_video = False
        self._last_pan_mouse_pos = None

        if hasattr(self, 'video_label'):
            self.video_label.setCursor(Qt.ArrowCursor)

        if hasattr(self, 'timeline_slider'):
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(0)
            self.timeline_slider.blockSignals(False)

        if hasattr(self, 'time_label'):
            self.time_label.setText("00:00 / 00:00")

        self.set_playback_paused(False, propagate=False, update_status=False)
        self.reset_video_zoom(silent=True)

    def set_playback_paused(self, paused, propagate=True, update_status=True):
        """Apply pause state to thread and sync playback button/action labels."""
        is_paused = bool(paused)

        if propagate and hasattr(self, 'thread') and self.thread is not None:
            self.thread.set_paused(is_paused)

        if hasattr(self, 'btn_pause_playback'):
            self.btn_pause_playback.setText("Resume" if is_paused else "Pause")

        if hasattr(self, 'action_toggle_playback'):
            self.action_toggle_playback.setText("Resume" if is_paused else "Pause")

        if update_status:
            state_text = "Paused" if is_paused else "Playing"
            self.statusBar().showMessage(f"Playback: {state_text}", 2000)

    def toggle_play_pause(self):
        """Toggle play/pause state."""
        if not hasattr(self, 'thread') or self.thread is None:
            return

        paused = self.thread.toggle_paused()
        self.set_playback_paused(paused, propagate=False)

    def seek_relative_seconds(self, delta_seconds):
        """Seek video timeline by relative seconds."""
        if not hasattr(self, 'thread') or self.thread is None:
            return
        self.thread.request_seek_relative(float(delta_seconds))

    def seek_backward_5s(self):
        """Seek backward 5 seconds."""
        self.seek_relative_seconds(-5.0)

    def seek_forward_5s(self):
        """Seek forward 5 seconds."""
        self.seek_relative_seconds(5.0)

    def _on_timeline_slider_pressed(self):
        """Mark that user is dragging the timeline slider."""
        self._timeline_user_dragging = True

    def _on_timeline_slider_released(self):
        """Seek to slider-selected timeline position."""
        self._timeline_user_dragging = False
        if not hasattr(self, 'thread') or self.thread is None:
            return

        duration = float(getattr(self, '_playback_duration_sec', 0.0) or 0.0)
        slider_max = max(1, self.timeline_slider.maximum())
        ratio = float(self.timeline_slider.value()) / float(slider_max)
        target_sec = duration * ratio if duration > 0 else 0.0
        self.thread.request_seek_to_seconds(target_sec)

    def update_playback_info(self, info):
        """Update timeline/time labels from VideoThread playback signal."""
        current_sec = float(info.get('current_sec', 0.0) or 0.0)
        duration_sec = float(info.get('duration_sec', 0.0) or 0.0)
        paused = bool(info.get('paused', False))

        self._playback_duration_sec = max(0.0, duration_sec)
        self.set_playback_paused(paused, propagate=False, update_status=False)

        if hasattr(self, 'timeline_slider') and not self._timeline_user_dragging:
            if self._playback_duration_sec > 0:
                ratio = max(0.0, min(1.0, current_sec / self._playback_duration_sec))
                slider_value = int(round(ratio * self.timeline_slider.maximum()))
            else:
                slider_value = 0

            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(slider_value)
            self.timeline_slider.blockSignals(False)

        if hasattr(self, 'time_label'):
            self.time_label.setText(
                f"{self._format_time_seconds(current_sec)} / {self._format_time_seconds(self._playback_duration_sec)}"
            )

    def _set_video_zoom(self, zoom_factor, silent=False):
        """Set zoom factor and refresh current frame display."""
        clamped = max(self.video_min_zoom, min(self.video_max_zoom, float(zoom_factor)))
        self.video_zoom_factor = clamped

        if clamped <= 1.0:
            self.video_pan_x = 0.0
            self.video_pan_y = 0.0
            self.is_panning_video = False
            self._last_pan_mouse_pos = None

        if hasattr(self, 'zoom_label'):
            self.zoom_label.setText(f"{clamped:.2f}x")

        if hasattr(self, 'video_label'):
            if clamped > 1.0 and not self.is_panning_video:
                self.video_label.setCursor(Qt.OpenHandCursor)
            elif clamped <= 1.0:
                self.video_label.setCursor(Qt.ArrowCursor)

        if hasattr(self, 'current_frame') and self.current_frame is not None:
            self.update_image(self.current_frame)

        if not silent:
            self.statusBar().showMessage(f"Zoom: {clamped:.2f}x", 1500)

    def zoom_in_video(self):
        """Increase video zoom."""
        self._set_video_zoom(self.video_zoom_factor + self.video_zoom_step)

    def zoom_out_video(self):
        """Decrease video zoom."""
        self._set_video_zoom(self.video_zoom_factor - self.video_zoom_step)

    def reset_video_zoom(self, silent=False):
        """Reset video zoom to 1x."""
        self._set_video_zoom(1.0, silent=silent)
    
    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

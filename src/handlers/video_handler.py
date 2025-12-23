"""
Video Handler Mixin - Handles video loading and management
"""
import cv2
from PyQt5.QtWidgets import QFileDialog


def _get_globals():
    """Lazy import to avoid circular dependency"""
    import integrated_main
    return integrated_main


class VideoHandlerMixin:
    """Mixin class for video management functionality"""
    
    def select_video(self):
        """Select and load a new video file"""
        g = _get_globals()
        
        # Access globals
        VIOLATOR_TRACK_IDS = g.VIOLATOR_TRACK_IDS
        RED_LIGHT_VIOLATORS = g.RED_LIGHT_VIOLATORS
        LANE_VIOLATORS = g.LANE_VIOLATORS
        PASSED_VEHICLES = g.PASSED_VEHICLES
        MOTORBIKE_COUNT = g.MOTORBIKE_COUNT
        CAR_COUNT = g.CAR_COUNT
        ALLOWED_VEHICLE_IDS = g.ALLOWED_VEHICLE_IDS
        VEHICLE_CLASSES = g.VEHICLE_CLASSES
        LANE_CONFIGS = g.LANE_CONFIGS
        TL_ROIS = g.TL_ROIS
        DIRECTION_ROIS = g.DIRECTION_ROIS
        is_on_stop_line = g.is_on_stop_line
        
        # Import functions from detection module
        from app.detection import check_tl_violation
        from app.geometry import point_in_polygon
        
        # Import VideoThread
        from core import VideoThread
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*.*)"
        )
        
        if file_path:
            # Stop current thread
            self.thread.stop()
            
            # Start new thread with selected video
            self.video_path = file_path
            self.thread = VideoThread(self.video_path)
            self.thread.change_pixmap_signal.connect(self.update_image)
            self.thread.error_signal.connect(self.show_error)
            
            # Pass globals reference to thread
            # Use lambda for _show_all_boxes to get real-time value
            self.thread.set_globals_reference({
                'ALLOWED_VEHICLE_IDS': ALLOWED_VEHICLE_IDS,
                'VEHICLE_CLASSES': VEHICLE_CLASSES,
                'LANE_CONFIGS': LANE_CONFIGS,
                'TL_ROIS': TL_ROIS,
                'DIRECTION_ROIS': DIRECTION_ROIS,
                'get_show_all_boxes': lambda: getattr(g, '_show_all_boxes', True),
                'is_on_stop_line': is_on_stop_line,
                'check_tl_violation': check_tl_violation,
                'point_in_polygon': point_in_polygon,
                'VIOLATOR_TRACK_IDS': VIOLATOR_TRACK_IDS,
                'RED_LIGHT_VIOLATORS': RED_LIGHT_VIOLATORS,
                'LANE_VIOLATORS': LANE_VIOLATORS,
                'PASSED_VEHICLES': PASSED_VEHICLES,
                'MOTORBIKE_COUNT': MOTORBIKE_COUNT,
                'CAR_COUNT': CAR_COUNT
            })
            
            self.thread.start()
            
            # Store cap for TL detection
            self.cap = cv2.VideoCapture(self.video_path)
            
            self.status_label.setText(f"Status: Loaded {file_path.split('/')[-1]}")
            print(f"📹 Loaded video: {file_path}")
            
            # Reset detection state
            g._detection_running = False
            VIOLATOR_TRACK_IDS.clear()
            RED_LIGHT_VIOLATORS.clear()
            LANE_VIOLATORS.clear()
            PASSED_VEHICLES.clear()
            self.btn_start.setText("Start Detection")
            
            # Try to auto-load configuration for this video
            if self.config_manager.config_exists(file_path):
                print(f"🔍 Found existing configuration for this video")
                if self.auto_load_configuration():
                    self.config_status_label.setText(f"✅ Config: Auto-loaded from file")
                    self.config_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                    self.status_label.setText(f"Status: Loaded {file_path.split('/')[-1]} [Config auto-loaded]")
                    return
            
            # No config found - reset ROIs for new video
            TL_ROIS.clear()
            LANE_CONFIGS.clear()
            DIRECTION_ROIS.clear()
            self.lane_list.clear()
            self.direction_roi_list.clear()
            self.ref_vector_p1 = None
            self.ref_vector_p2 = None
            self.ref_vector_label.setText("Ref Vector: Not set")
            self.tl_tracking_active = False
            self.config_status_label.setText("Config: No saved config found")
            self.config_status_label.setStyleSheet("QLabel { color: orange; font-style: italic; }")
            print("♻️ All ROIs reset. Draw new configuration or load from file.")
    
    def show_error(self, error_msg):
        """Display error message"""
        self.status_label.setText(f"Status: Error - {error_msg}")
        print(f"❌ Error: {error_msg}")

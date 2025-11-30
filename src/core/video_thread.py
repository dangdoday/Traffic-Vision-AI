"""
Video Thread - Xử lý video và detection trong background thread
"""
import cv2
import numpy as np
import time
from PyQt5.QtCore import QThread, pyqtSignal

from core import VehicleTracker, ViolationDetector, StopLineManager, TrafficLightManager


class VideoThread(QThread):
    """Thread xử lý video và YOLO detection"""
    
    change_pixmap_signal = pyqtSignal(np.ndarray)
    error_signal = pyqtSignal(str)
    
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self._run_flag = True
        self.model = None
        self.detection_enabled = False
        self.model_loaded = False
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = None
        self.realtime_mode = True  # Toggle realtime sync
        
        # Model config (will be set by MainWindow)
        self.model_config = None
        
        # Detailed FPS tracking
        self.processed_fps = 0  # Frames actually processed (with detection)
        self.processed_count = 0
        self.skipped_frames = 0  # Frames skipped in realtime mode
        
        # Initialize OOP modules
        self.vehicle_tracker = VehicleTracker(time_window=1.0, min_distance=20.0)
        self.violation_detector = ViolationDetector()
        self.stopline_manager = StopLineManager()
        self.traffic_light_manager = TrafficLightManager()
        
        # Reference to global state (will be set externally)
        self.globals_ref = None
    
    def set_globals_reference(self, globals_dict):
        """Set reference to global state dictionary"""
        self.globals_ref = globals_dict
    
    def set_reference_angle(self, ref_angle: float):
        """Update reference angle for direction detection
        
        Args:
            ref_angle: Reference angle in degrees (-180 to 180) for straight direction
        """
        self.vehicle_tracker.set_ref_angle(ref_angle)
        print(f"🧭 VideoThread: Reference angle set to {ref_angle:.1f}°")
    
    def run(self):
        """Main video processing loop"""
        cap = cv2.VideoCapture(self.video_path)
        self.fps_start_time = time.time()
        
        # Get video FPS
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps == 0:
            video_fps = 30
        
        frame_interval = 1.0 / video_fps
        next_frame_time = time.time()
        
        print(f"📹 Video FPS: {video_fps}, Frame interval: {frame_interval:.4f}s")
        print(f"⏱️ Realtime mode: {'ON (may skip frames)' if self.realtime_mode else 'OFF (process all frames)'}")
        
        while self._run_flag:
            current_time = time.time()
            
            if self.realtime_mode:
                # REALTIME MODE: Skip frames to match real-time
                if current_time >= next_frame_time:
                    ret, frame = cap.read()
                    if ret:
                        self.frame_count += 1
                        
                        # Track FPS
                        if time.time() - self.fps_start_time >= 1.0:
                            self.fps = self.frame_count
                            self.processed_fps = self.processed_count
                            print(f"📊 Display FPS: {self.fps} | Detection FPS: {self.processed_fps} | Skipped: {self.skipped_frames}")
                            self.frame_count = 0
                            self.processed_count = 0
                            self.skipped_frames = 0
                            self.fps_start_time = time.time()
                        
                        if self.detection_enabled and self.model is not None and self.model_loaded:
                            try:
                                frame = self.process_detection(frame)
                                self.processed_count += 1  # Count actual detections
                            except Exception as e:
                                print(f"⚠️ Detection error: {e}")
                                self.error_signal.emit(str(e))
                                self.detection_enabled = False
                        
                        self.change_pixmap_signal.emit(frame)
                        
                        next_frame_time += frame_interval
                        
                        # If falling behind, reset
                        if next_frame_time < current_time:
                            next_frame_time = current_time + frame_interval
                    else:
                        # Video ended, loop back
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self._clear_all_state()
                        next_frame_time = time.time()
                else:
                    self.skipped_frames += 1  # Count skipped frames
                    self.msleep(1)
            else:
                # FULL PROCESSING MODE: Process every frame (no skip)
                ret, frame = cap.read()
                if ret:
                    self.frame_count += 1
                    
                    # Track FPS
                    if time.time() - self.fps_start_time >= 1.0:
                        self.fps = self.frame_count
                        self.processed_fps = self.processed_count
                        print(f"📊 Display FPS: {self.fps} | Detection FPS: {self.processed_fps}")
                        self.frame_count = 0
                        self.processed_count = 0
                        self.fps_start_time = time.time()
                    
                    if self.detection_enabled and self.model is not None and self.model_loaded:
                        try:
                            frame = self.process_detection(frame)
                            self.processed_count += 1  # Count actual detections
                        except Exception as e:
                            print(f"⚠️ Detection error: {e}")
                            self.error_signal.emit(str(e))
                            self.detection_enabled = False
                    
                    self.change_pixmap_signal.emit(frame)
                else:
                    # Video ended, loop back
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self._clear_all_state()
            
        cap.release()
    
    def _clear_all_state(self):
        """Clear all tracking and violation state"""
        # Clear OOP modules
        self.vehicle_tracker.clear()
        self.violation_detector.clear()
        
        # Also clear global sets for backward compatibility
        if self.globals_ref:
            self.globals_ref['VIOLATOR_TRACK_IDS'].clear()
            self.globals_ref['RED_LIGHT_VIOLATORS'].clear()
            self.globals_ref['LANE_VIOLATORS'].clear()
            self.globals_ref['PASSED_VEHICLES'].clear()
            self.globals_ref['MOTORBIKE_COUNT'].clear()
            self.globals_ref['CAR_COUNT'].clear()
    
    def set_model(self, model):
        """Set pre-loaded model from main thread"""
        self.model = model
        self.model_loaded = True
        print("✅ Model set in thread")
    
    def process_detection(self, frame):
        """Process YOLO detection on frame"""
        if not self.globals_ref:
            return frame
        
        # Get global state references
        ALLOWED_VEHICLE_IDS = self.globals_ref['ALLOWED_VEHICLE_IDS']
        VEHICLE_CLASSES = self.globals_ref['VEHICLE_CLASSES']
        LANE_CONFIGS = self.globals_ref['LANE_CONFIGS']
        TL_ROIS = self.globals_ref['TL_ROIS']
        # Don't cache _show_all_boxes - read it fresh each time to get latest value
        is_on_stop_line = self.globals_ref['is_on_stop_line']
        check_tl_violation = self.globals_ref['check_tl_violation']
        point_in_polygon = self.globals_ref['point_in_polygon']
        
        # Backward compat globals
        VIOLATOR_TRACK_IDS = self.globals_ref['VIOLATOR_TRACK_IDS']
        RED_LIGHT_VIOLATORS = self.globals_ref['RED_LIGHT_VIOLATORS']
        LANE_VIOLATORS = self.globals_ref['LANE_VIOLATORS']
        PASSED_VEHICLES = self.globals_ref['PASSED_VEHICLES']
        MOTORBIKE_COUNT = self.globals_ref['MOTORBIKE_COUNT']
        CAR_COUNT = self.globals_ref['CAR_COUNT']
        
        # Get model config or use defaults
        imgsz = 416
        conf = 0.3
        classes = [0, 1, 2, 3, 4]  # allow all trained classes by default
        
        if self.model_config:
            imgsz = self.model_config.get('default_imgsz', imgsz)
            conf = self.model_config.get('default_conf', conf)
            classes = self.model_config.get('classes', classes)
        
        # Run YOLO tracking with dynamic config
        results = self.model.track(
            frame,
            tracker="bytetrack.yaml",
            persist=True,
            classes=classes,
            verbose=False,
            imgsz=imgsz,
            conf=conf
        )
        
        vehicles = []
        
        if results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                if cls_id in ALLOWED_VEHICLE_IDS:
                    track_id = int(box.id[0]) if box.id is not None else -1
                    vehicles.append({
                        "track_id": track_id,
                        "cls_id": cls_id,
                        "box": (x1, y1, x2, y2),
                        "conf": conf_val
                    })
        
        # Process vehicles with direction detection
        for veh in vehicles:
            track_id = veh["track_id"]
            cls_id = veh["cls_id"]
            x1, y1, x2, y2 = veh["box"]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            vehicle_label = VEHICLE_CLASSES.get(cls_id, "vehicle")
            
            # Track vehicle position for direction calculation using OOP
            if track_id != -1:
                vehicle_direction = self.vehicle_tracker.update_position(track_id, cx, cy)
                
                # Check if vehicle crossed THE stop line
                if is_on_stop_line(cx, cy, threshold=20):
                    if not self.violation_detector.passed_vehicles.__contains__(track_id):
                        # ⚠️ CRITICAL: Đánh dấu điểm bắt đầu khi xe VỪA qua stopline
                        self.vehicle_tracker.mark_stopline_crossing(track_id, cx, cy)
                        
                        # Mark vehicle as passed and count by type
                        self.violation_detector.mark_vehicle_passed(track_id, cls_id)
                        
                        # Also update global sets for backward compatibility
                        PASSED_VEHICLES.add(track_id)
                        if cls_id in [2, 3]:  # xe đạp, xe máy
                            MOTORBIKE_COUNT.add(track_id)
                        elif cls_id in [0, 1, 4]:  # ô tô, xe bus, xe tải
                            CAR_COUNT.add(track_id)
                        
                        # Debug: Print TL states when vehicle crosses
                        if len(TL_ROIS) > 0:
                            tl_states = [f"{tl_type}:{color}" for _, _, _, _, tl_type, color in TL_ROIS]
                            print(f"🚦 Vehicle crossing: {vehicle_label} (ID={track_id}) Dir={vehicle_direction} | TL states: {tl_states}")
                        
                        # Check for TL violation using direction and OOP
                        is_violation, reason = check_tl_violation(track_id, vehicle_direction)
                        if is_violation:
                            self.violation_detector.add_violation(track_id, 'red_light')
                            # Update globals for backward compatibility
                            RED_LIGHT_VIOLATORS.add(track_id)
                            VIOLATOR_TRACK_IDS.add(track_id)
                            print(f"🚨 TL VIOLATION: {vehicle_label} (ID={track_id}) Dir={vehicle_direction} - {reason}")
                        else:
                            print(f"✅ Vehicle passed: {vehicle_label} (ID={track_id}) Dir={vehicle_direction} - {reason}")
            
            # Check lane violation
            for lane in LANE_CONFIGS:
                poly = lane["poly"]
                allowed = lane.get("allowed_labels", ["all"])
                
                if point_in_polygon((cx, cy), poly):
                    # Check if vehicle type is allowed in this lane
                    if "all" not in allowed and vehicle_label not in allowed:
                        if not self.violation_detector.lane_violators.__contains__(track_id):
                            self.violation_detector.add_violation(track_id, 'lane')
                            # Update globals for backward compatibility
                            LANE_VIOLATORS.add(track_id)
                            VIOLATOR_TRACK_IDS.add(track_id)
                            print(f"🚨 LANE VIOLATION: {vehicle_label} (ID={track_id}) in restricted lane!")
                    break
            
            # Draw vehicle (respect _show_all_boxes flag)
            is_violator = self.violation_detector.is_violator(track_id)
            
            # ⚠️ CRITICAL: Only show RED box if vehicle is violator AND has passed stopline
            has_passed_stopline = track_id in PASSED_VEHICLES
            show_as_violator = is_violator and has_passed_stopline
            
            # Get real-time _show_all_boxes value via lambda function
            get_show_all_boxes = self.globals_ref.get('get_show_all_boxes')
            _show_all_boxes = get_show_all_boxes() if get_show_all_boxes else True
            
            # Only draw if: _show_all_boxes=True OR vehicle is violator (and passed)
            if _show_all_boxes or show_as_violator:
                box_color = (0, 0, 255) if show_as_violator else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                
                label_text = f"{vehicle_label} ID:{track_id}"
                if show_as_violator:
                    label_text += " [VIOLATOR]"
                
                cv2.putText(frame, label_text, (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
        
        # Draw statistics panel
        frame = self._draw_statistics_panel(frame)
        
        return frame
    
    def _draw_statistics_panel(self, frame):
        """Draw statistics panel on frame"""
        # Panel position - TOP LEFT
        panel_x = 10
        panel_y = 10
        panel_width = 550
        panel_height = 100
        
        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (50, 50, 50), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Get statistics from OOP module
        stats = self.violation_detector.get_statistics()
        
        # Draw stats in 3 rows
        text_y = panel_y + 28
        
        # Row 1: FPS info
        cv2.putText(frame, f"Render FPS: {self.fps}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        if self.detection_enabled:
            cv2.putText(frame, f"Detection FPS: {self.processed_fps}", (panel_x + 230, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
        
        # Row 2: Vehicle counts (from OOP)
        text_y += 32
        cv2.putText(frame, f"Xe may: {stats['motorbikes']}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"O to: {stats['cars']}", (panel_x + 150, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Total: {stats['total_vehicles']}", (panel_x + 280, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
        
        # Row 3: Violations (from OOP)
        text_y += 32
        cv2.putText(frame, f"TL Violations: {stats['red_light_violations']}", (panel_x + 10, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
        cv2.putText(frame, f"Lane Violations: {stats['lane_violations']}", (panel_x + 280, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 165, 255), 2)
        
        return frame
    
    def stop(self):
        """Stop the thread"""
        self._run_flag = False
        self.wait()

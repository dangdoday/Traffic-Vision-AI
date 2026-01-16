"""
Video Thread - Xử lý video và detection trong background thread
"""
import cv2
import numpy as np
import time
from PyQt5.QtCore import QThread, pyqtSignal

from core import VehicleTracker, ViolationDetector, StopLineManager, TrafficLightManager

# PaddleOCR for license plate text recognition
try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
    print("✅ PaddleOCR imported successfully")
except Exception as e:
    print(f"⚠️ PaddleOCR not available: {e}")
    print("   Install: pip install paddleocr paddlepaddle")
    PADDLE_OCR_AVAILABLE = False


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
        self.target_display_fps = 30  # Limit display FPS to reduce CPU usage
        
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
        
        # License plate relative position tracking
        # Format: {vehicle_track_id: {'x_ratio': float, 'y_ratio': float, 'abs_w': int, 'abs_h': int, 'conf': float, 'last_updated_frame': int, 'ocr_text': str}}
        # Note: x_ratio, y_ratio are relative (0.0-1.0), but abs_w, abs_h are absolute pixels to keep plate size constant
        self.vehicle_plate_positions = {}
        self.update_interval = 30  # Update relative position every 30 frames
        self.current_frame_count = 0
        self.use_plate_relative_tracking = True  # Toggle between YOLO direct vs relative tracking
        
        # Initialize PaddleOCR
        self.ocr = None
        self.enable_ocr = True  # Toggle OCR on/off
        if PADDLE_OCR_AVAILABLE and self.enable_ocr:
            try:
                # use_textline_orientation=True: detect rotated text
                # lang='en': English (use 'ch' for Chinese, 'latin' for Latin scripts)
                self.ocr = PaddleOCR(use_textline_orientation=True, lang='en')
                print("✅ PaddleOCR initialized for license plate recognition")
            except Exception as e:
                print(f"⚠️ Failed to initialize PaddleOCR: {e}")
                self.ocr = None
        
        # Reference to global state (will be set externally)
        self.globals_ref = None
    
    def set_globals_reference(self, globals_dict):
        """Set reference to global state dictionary"""
        self.globals_ref = globals_dict
    
    def recognize_plate_text(self, frame_original, plate_bbox):
        """Run OCR on license plate region from original frame
        
        Args:
            frame_original: Original full-size frame
            plate_bbox: (x1, y1, x2, y2) of plate in original coordinates
            
        Returns:
            str: Recognized text or empty string
        """
        if self.ocr is None:
            return ""
        
        try:
            x1, y1, x2, y2 = plate_bbox
            
            # Ensure valid crop coordinates
            h, w = frame_original.shape[:2]
            x1 = max(0, min(x1, w-1))
            y1 = max(0, min(y1, h-1))
            x2 = max(x1+1, min(x2, w))
            y2 = max(y1+1, min(y2, h))
            
            # Crop plate region from ORIGINAL frame
            plate_img = frame_original[y1:y2, x1:x2]
            
            if plate_img.size == 0:
                return ""
            
            # Run OCR
            result = self.ocr.predict(plate_img)
            
            if result and result[0]:
                # Extract text from all detected lines
                texts = []
                for line in result[0]:
                    if line[1][0]:  # Check if text exists
                        text = line[1][0].strip()
                        conf = line[1][1]
                        if conf > 0.5:  # Only keep high confidence
                            texts.append(text)
                
                return ' '.join(texts) if texts else ""
            
            return ""
            
        except Exception as e:
            # Silently fail OCR errors to not disrupt detection
            return ""
    
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
        print(f"🎯 Target display FPS: {self.target_display_fps}")
        
        # Display frame interval for limiting GUI updates
        display_interval = 1.0 / self.target_display_fps
        last_display_time = 0
        
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
                        
                        # Only emit to GUI at target display FPS to reduce CPU
                        if current_time - last_display_time >= display_interval:
                            self.change_pixmap_signal.emit(frame)
                            last_display_time = current_time
                        
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
                    # ⚠️ PERFORMANCE: Sleep 10ms instead of 1ms to reduce CPU spin
                    self.msleep(10)
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
                    
                    # Only emit to GUI at target display FPS
                    if current_time - last_display_time >= display_interval:
                        self.change_pixmap_signal.emit(frame)
                        last_display_time = current_time
                    
                    # ⚠️ PERFORMANCE: Small sleep to yield CPU
                    self.msleep(5)
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
        
        # Clear license plate positions
        self.vehicle_plate_positions.clear()
        self.current_frame_count = 0
        
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
        """Process YOLO detection on original frame
        
        Args:
            frame: Original full-size frame
        
        Returns:
            frame: Frame with drawings (same as input)
        """
        if not self.globals_ref:
            return frame
        
        # Keep original frame size for display and OCR
        frame_original = frame
        orig_h, orig_w = frame.shape[:2]
        
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
        classes = [0, 1, 3, 4]
        
        if self.model_config:
            imgsz = self.model_config.get('default_imgsz', 416)
            conf = self.model_config.get('default_conf', 0.3)
            classes = self.model_config.get('classes', [0, 1, 3, 4])
        
        # Run YOLO tracking with dynamic config
        # YOLO will resize image internally according to imgsz
        results = self.model.track(
            frame,
            tracker="bytetrack.yaml",
            persist=True,
            classes=classes,
            verbose=False,
            imgsz=imgsz,
            conf=conf
        )
        
        # Calculate scale factors from YOLO resized size back to original
        # YOLO returns bbox in original coordinates already? Let's check
        # If bbox looks wrong, we need to scale it
        
        vehicles = []
        license_plates = []
        
        if results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                # YOLO bbox is already in original frame coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                if cls_id in ALLOWED_VEHICLE_IDS:
                    track_id = int(box.id[0]) if box.id is not None else -1
                    
                    if cls_id == 5:  # License plate
                        if self.use_plate_relative_tracking:
                            # Relative tracking mode: separate plates
                            license_plates.append({
                                "track_id": track_id,
                                "box": (x1, y1, x2, y2),
                                "conf": conf_val
                            })
                        else:
                            # YOLO direct mode: treat plates as normal vehicles
                            vehicles.append({
                                "track_id": track_id,
                                "cls_id": cls_id,
                                "box": (x1, y1, x2, y2),
                                "conf": conf_val
                            })
                    else:  # Vehicle (not plate)
                        vehicles.append({
                            "track_id": track_id,
                            "cls_id": cls_id,
                            "box": (x1, y1, x2, y2),
                            "conf": conf_val
                        })
        
        # === MAP LICENSE PLATES TO VEHICLES (RELATIVE POSITION) ===
        # Only do mapping if relative tracking mode is enabled
        if self.use_plate_relative_tracking:
            self.current_frame_count += 1
        
        current_vehicle_ids = set()
        for veh in vehicles:
            if veh["track_id"] != -1:
                current_vehicle_ids.add(veh["track_id"])
        
        # Check each detected plate
        for plate in license_plates:
            plate_x1, plate_y1, plate_x2, plate_y2 = plate["box"]
            plate_cx = (plate_x1 + plate_x2) / 2.0
            plate_cy = (plate_y1 + plate_y2) / 2.0
            plate_w = plate_x2 - plate_x1
            plate_h = plate_y2 - plate_y1
            
            # Expand plate bbox by 40% for better matching when vehicle bbox changes
            # This creates a tolerance zone to catch plates even when vehicle bbox fluctuates
            expand_ratio = 0.40
            expand_w = plate_w * expand_ratio
            expand_h = plate_h * expand_ratio
            plate_x1_expanded = plate_x1 - expand_w / 2
            plate_y1_expanded = plate_y1 - expand_h / 2
            plate_x2_expanded = plate_x2 + expand_w / 2
            plate_y2_expanded = plate_y2 + expand_h / 2
            
            # Find which vehicle contains this plate
            best_match = None
            best_overlap = 0
            
            for veh in vehicles:
                veh_x1, veh_y1, veh_x2, veh_y2 = veh["box"]
                veh_track_id = veh["track_id"]
                
                if veh_track_id == -1:
                    continue
                
                # Check if plate center is inside vehicle bbox
                if veh_x1 <= plate_cx <= veh_x2 and veh_y1 <= plate_cy <= veh_y2:
                    # Calculate overlap score using EXPANDED plate bbox
                    overlap_x1 = max(plate_x1_expanded, veh_x1)
                    overlap_y1 = max(plate_y1_expanded, veh_y1)
                    overlap_x2 = min(plate_x2_expanded, veh_x2)
                    overlap_y2 = min(plate_y2_expanded, veh_y2)
                    
                    if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                        overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                        # Use expanded plate area for ratio calculation
                        plate_area_expanded = (plate_x2_expanded - plate_x1_expanded) * (plate_y2_expanded - plate_y1_expanded)
                        overlap_ratio = overlap_area / plate_area_expanded if plate_area_expanded > 0 else 0
                        
                        if overlap_ratio > best_overlap:
                            best_overlap = overlap_ratio
                            best_match = veh
            
            # If found matching vehicle, calculate and store relative position
            # OVERLAP THRESHOLD (0.5 = 50%): Minimum percentage of plate area that must be inside vehicle bbox
            # - Too low (e.g., 0.1): Risk assigning plate to wrong vehicle (false positive)
            # - Too high (e.g., 0.9): May miss valid plates when bbox changes (false negative)
            # - 0.5 (50%): Good balance - plate must be mostly inside vehicle to be assigned
            if best_match and best_overlap > 0.5:  # At least 50% overlap required
                veh_track_id = best_match["track_id"]
                veh_x1, veh_y1, veh_x2, veh_y2 = best_match["box"]
                
                veh_w = veh_x2 - veh_x1
                veh_h = veh_y2 - veh_y1
                
                if veh_w > 0 and veh_h > 0:
                    # Check if we should update (first time OR 30 frames passed)
                    should_update = False
                    if veh_track_id not in self.vehicle_plate_positions:
                        should_update = True  # First detection
                    else:
                        last_updated = self.vehicle_plate_positions[veh_track_id].get('last_updated_frame', 0)
                        frames_since_update = self.current_frame_count - last_updated
                        if frames_since_update >= self.update_interval:
                            should_update = True  # Time to refresh
                    
                    if should_update:
                        # Calculate relative position for x,y (0.0 to 1.0)
                        x_ratio = (plate_x1 - veh_x1) / veh_w
                        y_ratio = (plate_y1 - veh_y1) / veh_h
                        
                        # Store ABSOLUTE size (not ratio) to keep plate size constant
                        abs_w = int(plate_w)
                        abs_h = int(plate_h)
                        
                        # Run OCR on plate ONLY if this vehicle doesn't have text yet
                        ocr_text = ""
                        if veh_track_id in self.vehicle_plate_positions:
                            # Keep existing OCR text if available
                            ocr_text = self.vehicle_plate_positions[veh_track_id].get('ocr_text', '')
                        
                        # Only run OCR if no text exists yet
                        if not ocr_text and self.ocr is not None:
                            plate_bbox = (int(plate_x1), int(plate_y1), int(plate_x2), int(plate_y2))
                            ocr_text = self.recognize_plate_text(frame_original, plate_bbox)
                            if ocr_text:
                                print(f"🔤 OCR Vehicle ID:{veh_track_id} → '{ocr_text}'")
                            else:
                                print(f"⚠️ OCR Vehicle ID:{veh_track_id} → No text detected")
                        
                        # Store or update relative position
                        self.vehicle_plate_positions[veh_track_id] = {
                            'x_ratio': x_ratio,
                            'y_ratio': y_ratio,
                            'abs_w': abs_w,  # Absolute width (pixels)
                            'abs_h': abs_h,  # Absolute height (pixels)
                            'conf': plate["conf"],
                            'last_updated_frame': self.current_frame_count,
                            'ocr_text': ocr_text  # OCR recognized text
                        }
        
            # Clean up plates for vehicles that are no longer tracked
            for veh_id in list(self.vehicle_plate_positions.keys()):
                if veh_id not in current_vehicle_ids:
                    del self.vehicle_plate_positions[veh_id]
        
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
                
                # Draw license plate if we have relative position for this vehicle (only in relative tracking mode)
                if self.use_plate_relative_tracking and track_id in self.vehicle_plate_positions:
                    plate_info = self.vehicle_plate_positions[track_id]
                    
                    # Calculate absolute position from relative position (x,y move with vehicle)
                    veh_w = x2 - x1
                    veh_h = y2 - y1
                    
                    plate_x1 = int(x1 + plate_info['x_ratio'] * veh_w)
                    plate_y1 = int(y1 + plate_info['y_ratio'] * veh_h)
                    
                    # Use ABSOLUTE size (keep original plate size, don't scale with vehicle)
                    plate_w = plate_info['abs_w']
                    plate_h = plate_info['abs_h']
                    plate_x2 = plate_x1 + plate_w
                    plate_y2 = plate_y1 + plate_h
                    
                    # Draw plate box in yellow/orange
                    plate_color = (0, 255, 255)  # Yellow
                    cv2.rectangle(frame, (plate_x1, plate_y1), (plate_x2, plate_y2), plate_color, 2)
                    
                    # Add OCR text if available
                    ocr_text = plate_info.get('ocr_text', '')
                    if ocr_text:
                        label_text += f" [{ocr_text}]"
                        
                        # Draw OCR text near plate
                        cv2.putText(frame, ocr_text, (plate_x1, plate_y1 - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    else:
                        label_text += " [PLATE]"
                
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

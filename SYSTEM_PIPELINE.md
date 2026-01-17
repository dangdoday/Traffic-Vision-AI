# Traffic Vision AI - System Pipeline

## 🎯 Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│                    (PyQt5 - integrated_main.py)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Video    │  │ Settings │  │ ROI      │  │ Display  │       │
│  │ Controls │  │ Menu     │  │ Editor   │  │ Canvas   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO PROCESSING THREAD                       │
│                     (core/video_thread.py)                       │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. VIDEO FRAME CAPTURE                                    │  │
│  │    • Read frame from video file/camera                    │  │
│  │    • Skip frames if needed (FPS control)                  │  │
│  │    • Get original frame for OCR cropping                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. YOLO DETECTION                                         │  │
│  │    • Input: Frame                                         │  │
│  │    • Model: YOLOv8 (models/yolov8/*.pt)                  │  │
│  │    • Classes: [0=car, 1=bus, 2=bicycle,                  │  │
│  │               3=motorbike, 4=truck, 5=license_plate]     │  │
│  │    • Output: Detections with bboxes                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3. SEPARATION                                             │  │
│  │    • Split detections into:                               │  │
│  │      - Vehicles (class 0,1,2,3,4)                        │  │
│  │      - Plates (class 5)                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    ▼                   ▼                         │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │ 4a. VEHICLE TRACKING    │  │ 4b. PLATE DETECTION     │      │
│  │     (ByteTrack)         │  │     (YOLO Direct Mode)  │      │
│  │  • Assign track_id      │  │  • Detect plates        │      │
│  │  • Update trajectories  │  │  • Get plate bboxes     │      │
│  │  • Maintain history     │  │                         │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│              │                             │                     │
│              └──────────┬──────────────────┘                     │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 5. PLATE-TO-VEHICLE MAPPING                               │  │
│  │    • For each detected plate:                             │  │
│  │      - Check if 100% inside any vehicle bbox              │  │
│  │      - Map: vehicle_to_plate_map[veh_id] = plate_id      │  │
│  │    • Store plate track_id for real-time bbox lookup      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 6. OCR PROCESSING (if enabled)                            │  │
│  │    • For each mapped plate (first time only):             │  │
│  │      ┌────────────────────────────────────────────────┐  │  │
│  │      │ 6.1. Get plate bbox from current detections    │  │  │
│  │      │      (using stored track_id)                    │  │  │
│  │      └────────────────────────────────────────────────┘  │  │
│  │                        │                                   │  │
│  │                        ▼                                   │  │
│  │      ┌────────────────────────────────────────────────┐  │  │
│  │      │ 6.2. Crop plate from ORIGINAL frame            │  │  │
│  │      │      • Get coordinates (x1,y1,x2,y2)           │  │  │
│  │      │      • Crop: plate_img = frame[y1:y2, x1:x2]   │  │  │
│  │      └────────────────────────────────────────────────┘  │  │
│  │                        │                                   │  │
│  │                        ▼                                   │  │
│  │      ┌────────────────────────────────────────────────┐  │  │
│  │      │ 6.3. Preprocessing                              │  │  │
│  │      │      • Resize to 100px height                   │  │  │
│  │      │      • Convert to grayscale                     │  │  │
│  │      │      • CLAHE contrast enhancement               │  │  │
│  │      │      • Bilateral filter (noise reduction)       │  │  │
│  │      │      • Sharpen with kernel                      │  │  │
│  │      │      • Convert back to BGR                      │  │  │
│  │      └────────────────────────────────────────────────┘  │  │
│  │                        │                                   │  │
│  │                        ▼                                   │  │
│  │      ┌────────────────────────────────────────────────┐  │  │
│  │      │ 6.4. PaddleOCR Recognition                      │  │  │
│  │      │      • ocr.predict(processed_img)               │  │  │
│  │      │      • Extract from result[0]['rec_texts']      │  │  │
│  │      │      • Filter by confidence > 0.5               │  │  │
│  │      │      • Clean: remove spaces and dots            │  │  │
│  │      └────────────────────────────────────────────────┘  │  │
│  │                        │                                   │  │
│  │                        ▼                                   │  │
│  │      ┌────────────────────────────────────────────────┐  │  │
│  │      │ 6.5. Store Result                               │  │  │
│  │      │      vehicle_ocr_texts[veh_id] = "30M04019"    │  │  │
│  │      └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 7. TRAFFIC LIGHT MONITORING                               │  │
│  │    • For each TL ROI:                                     │  │
│  │      - Crop ROI from frame                                │  │
│  │      - Convert to HSV                                     │  │
│  │      - Detect red/yellow/green by color range            │  │
│  │      - Update TL state                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 8. VIOLATION DETECTION                                    │  │
│  │    • Check each vehicle:                                  │  │
│  │      - Crosses stop line when light is red?              │  │
│  │      - Wrong direction in lane?                          │  │
│  │      - Speed violation?                                  │  │
│  │    • Log violations with vehicle ID + OCR text           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 9. DRAWING & VISUALIZATION                                │  │
│  │    • Draw vehicle bboxes (green)                          │  │
│  │    • Draw plate bboxes:                                   │  │
│  │      - Green (0,255,0) for YOLO Direct mode              │  │
│  │      - Yellow (0,255,255) for Relative mode              │  │
│  │    • Draw OCR text on plates and vehicles                │  │
│  │    • Draw traffic light ROIs with colors                 │  │
│  │    • Draw stop lines, lanes, direction arrows            │  │
│  │    • Draw violation indicators                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 10. EMIT SIGNAL TO UI                                     │  │
│  │     • frame_ready.emit(processed_frame)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DISPLAY ON UI CANVAS                        │
│                   • Update QLabel with frame                     │
│                   • Show violation logs                          │
│                   • Update statistics                            │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow Diagram

```
┌──────────┐
│  Video   │
│  Source  │
└────┬─────┘
     │
     ▼
┌─────────────┐      ┌──────────────┐
│   Frame     │─────▶│ YOLO Model   │
│  Original   │      │ (Detection)  │
└─────────────┘      └──────┬───────┘
     │                      │
     │                      ▼
     │              ┌──────────────┐
     │              │  Detections  │
     │              │ [Vehicles +  │
     │              │   Plates]    │
     │              └──────┬───────┘
     │                     │
     │              ┌──────┴───────┐
     │              │              │
     │              ▼              ▼
     │      ┌─────────────┐  ┌──────────┐
     │      │  Vehicles   │  │  Plates  │
     │      │ (ByteTrack) │  │  (Raw)   │
     │      └──────┬──────┘  └────┬─────┘
     │             │              │
     │             └──────┬───────┘
     │                    │
     │                    ▼
     │           ┌──────────────────┐
     │           │ Plate Mapping    │
     │           │ (100% inside)    │
     │           └────────┬─────────┘
     │                    │
     │                    ▼
     │           ┌──────────────────┐
     │           │ Get Plate BBox   │
     │           │ (by track_id)    │
     │           └────────┬─────────┘
     │                    │
     └────────────────────┼─────────┐
                          │         │
                          ▼         ▼
                    ┌──────────────────┐
                    │  Crop Plate from │
                    │  Original Frame  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Preprocessing   │
                    │ • Resize 100px   │
                    │ • CLAHE          │
                    │ • Bilateral      │
                    │ • Sharpen        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   PaddleOCR      │
                    │   .predict()     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Extract from     │
                    │ 'rec_texts' key  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Store OCR Text  │
                    │  to Vehicle      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Draw & Display   │
                    └──────────────────┘
```

## 🔧 Key Components

### 1. Models
- **Vehicle/Plate Detection**: `models/yolov8/416_vehicle_plate.pt`
- **OCR Engine**: PaddleOCR (lang='en')

### 2. Detection Modes
- **YOLO Direct** (Default): 
  - Plates detected by YOLO each frame
  - Green boxes (0,255,0)
  - Real-time bbox from current detections
  
- **Relative Position Tracking**:
  - Track plate position relative to vehicle
  - Yellow boxes (0,255,255)
  - Uses cached bbox

### 3. OCR Pipeline
```python
recognize_plate_text(frame_original, plate_bbox):
    1. Crop plate from original frame
    2. preprocess_plate():
       - resize to 100px height
       - grayscale
       - CLAHE (clipLimit=3.0)
       - bilateral filter (5, 75, 75)
       - sharpen kernel
       - convert back to BGR
    3. ocr.predict(processed)
    4. Extract result[0]['rec_texts']
    5. Filter by confidence > 0.5
    6. Clean text (remove spaces, dots)
    7. Return final text
```

### 4. Configuration System
- **Config Files**: `configs/*.json`
- **Stores**:
  - ROI definitions (traffic lights, stop lines, lanes)
  - Reference vectors for direction detection
  - Camera calibration parameters

### 5. State Management
- **Global State**: `src/app/globals.py`
- **Flags**:
  - `tl_tracking_active`: Enable/disable TL monitoring
  - `enable_ocr`: Toggle OCR processing
  - `use_plate_relative_tracking`: Switch detection modes

### 6. Data Structures
```python
# Vehicle tracking
vehicle_list = [
    {
        'track_id': int,
        'bbox': (x1, y1, x2, y2),
        'class_id': int,
        'label': str
    }
]

# Plate mapping (YOLO Direct)
vehicle_to_plate_map = {
    vehicle_track_id: plate_track_id
}

# OCR results
vehicle_ocr_texts = {
    vehicle_track_id: "30M04019"
}

# Traffic lights
TL_ROIS = [
    {
        'points': [(x1,y1), (x2,y2), (x3,y3), (x4,y4)],
        'current_color': 'red'/'yellow'/'green'
    }
]
```

## 🎨 Color Coding

| Element | Color | RGB | Usage |
|---------|-------|-----|-------|
| Vehicle Box | Green | (0, 255, 0) | All vehicles |
| Plate (YOLO Direct) | Green | (0, 255, 0) | Default mode |
| Plate (Relative) | Yellow | (0, 255, 255) | Alternative mode |
| OCR Text | Green | (0, 255, 0) | Plate text display |
| Red Light | Red | (0, 0, 255) | Traffic light ROI |
| Yellow Light | Yellow | (0, 255, 255) | Traffic light ROI |
| Green Light | Green | (0, 255, 0) | Traffic light ROI |
| Violation | Red | (0, 0, 255) | Violation indicator |

## 🚦 Processing Flow Summary

1. **Frame Capture** → Get current video frame
2. **Detection** → YOLO finds vehicles and plates
3. **Tracking** → ByteTrack assigns IDs
4. **Mapping** → Associate plates with vehicles (100% containment)
5. **OCR** → Read plate text with preprocessing
6. **TL Monitor** → Check traffic light states
7. **Violation Check** → Detect traffic violations
8. **Visualization** → Draw all elements
9. **Display** → Show on UI canvas

## ⚙️ Settings & Toggles

### Menu: Settings
- 🔤 **Enable/Disable OCR**: Toggle OCR processing
- 📷 **Plate Detection Mode**:
  - ✅ YOLO Direct Detection (default)
  - ⬜ Relative Position Tracking

### Menu: View
- 🚥 Traffic Light ROIs
- 🛑 Stop Lines
- 🛣️ Lanes
- 🧭 Direction Vectors

## 📝 Configuration Files

### Sample: `configs/video_config.json`
```json
{
    "TL_ROIS": [...],
    "STOPLINES": [...],
    "LANES": [...],
    "REFERENCE_VECTORS": [...],
    "VIDEO_PATH": "path/to/video.mp4"
}
```

## 🔍 Debugging

### Debug Flags
- Set in code or via UI
- Enable verbose logging for:
  - Detection results
  - OCR attempts
  - Mapping success/failure
  - Violation triggers

### Test Script
- **File**: `test_ocr.py`
- **Purpose**: Test OCR pipeline on single images
- **Features**:
  - File dialog for image selection
  - Full pipeline: YOLO → Map → OCR → Display
  - Debug image saving
  - Result visualization

---

**Last Updated**: January 17, 2026
**System Version**: Traffic Vision AI v2.0 (with improved OCR)

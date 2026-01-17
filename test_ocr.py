"""
Test OCR Pipeline
YOLO detection → Map plates to vehicles → OCR → Display result
"""
import cv2
import numpy as np
import sys
from tkinter import Tk, filedialog

try:
    from ultralytics import YOLO
    print("✅ YOLO OK")
except:
    print("❌ YOLO not available")
    sys.exit(1)

# Try EasyOCR first (better for license plates)
USE_EASYOCR = False
try:
    import easyocr
    print("✅ EasyOCR available - using it for better plate recognition")
    USE_EASYOCR = True
except:
    print("⚠️  EasyOCR not available, falling back to PaddleOCR")
    try:
        from paddleocr import PaddleOCR
        print("✅ PaddleOCR OK")
    except:
        print("❌ No OCR available")
        sys.exit(1)

VEHICLE_CLASSES = {0: 'car', 1: 'bus', 2: 'bicycle', 3: 'motorbike', 4: 'truck', 5: 'license_plate'}

def preprocess_plate(img):
    """Preprocessing giống Traffic-Vision-AI gốc"""
    # 1. Resize to height 100px
    h, w = img.shape[:2]
    if h < 100:
        scale = 100 / h
        img = cv2.resize(img, (int(w * scale), 100), interpolation=cv2.INTER_CUBIC)
    
    # 2. Grayscale
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. CLAHE contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    img = clahe.apply(img)
    
    # 4. Bilateral filter (noise reduction, keep edges)
    img = cv2.bilateralFilter(img, 5, 75, 75)
    
    # 5. Sharpen
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    img = cv2.filter2D(img, -1, kernel)
    
    return img


def run_ocr(ocr, frame, bbox, use_easyocr=False, save_debug=False):
    """Run OCR on plate region - using preprocessing from original project"""
    try:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        
        plate_img = frame[y1:y2, x1:x2]
        if plate_img.size == 0:
            return ""
        
        ph, pw = plate_img.shape[:2]
        print(f"    🔍 Original {pw}x{ph}")
        
        # Preprocess (giống họ)
        processed = preprocess_plate(plate_img)
        
        if save_debug:
            cv2.imwrite(f"debug_plate_{x1}_{y1}.jpg", processed)
            print(f"    💾 Saved processed plate")
        
        if use_easyocr:
            # EasyOCR needs BGR
            if len(processed.shape) == 2:
                processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            result = ocr.readtext(processed, detail=0, allowlist='0123456789ABCDEFGHKLMNPSTUVXYZ-.')
            text = "".join(result).replace(" ", "")
            return text
        else:
            # PaddleOCR needs BGR image (not grayscale)
            if len(processed.shape) == 2:
                processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            else:
                processed_bgr = processed
            
            result = ocr.predict(processed_bgr)
            
            # New PaddleOCR format returns dict with 'rec_texts' key
            if result and len(result) > 0:
                result_dict = result[0]
                if isinstance(result_dict, dict) and 'rec_texts' in result_dict:
                    texts = result_dict['rec_texts']
                    scores = result_dict.get('rec_scores', [])
                    
                    # Filter by confidence and join
                    filtered_texts = []
                    for i, text in enumerate(texts):
                        conf = scores[i] if i < len(scores) else 1.0
                        if conf > 0.5:  # Min confidence threshold
                            filtered_texts.append(str(text).strip())
                    
                    final_text = "".join(filtered_texts).replace(" ", "").replace(".", "")
                    print(f"    ✅ OCR found: {texts} (conf: {scores})")
                    print(f"    ✅ Final text: '{final_text}'")
                    return final_text
                else:
                    print(f"    ⚠️ Unexpected result format: {type(result_dict)}")
            else:
                print(f"    ⚠️ No text detected")
            return ""
            
    except Exception as e:
        print(f"    ❌ OCR error: {e}")
        return ""

def test_pipeline(image_path, model_path="models/yolov8/416_vehicle_plate.pt"):
    """Test full OCR pipeline"""
    print(f"\n{'='*60}")
    print("🧪 TEST OCR PIPELINE")
    print(f"📁 Image: {image_path}")
    print(f"🤖 Model: {model_path}")
    print(f"{'='*60}")
    
    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        print("❌ Cannot load image")
        return
    
    h, w = frame.shape[:2]
    print(f"\n📐 Image size: {w}x{h}")
    
    # Load YOLO
    print("\n🔄 Loading YOLO model...")
    model = YOLO(model_path)
    print("✅ YOLO loaded")
    
    # Init OCR
    print(f"\n🚀 Initializing {'EasyOCR' if USE_EASYOCR else 'PaddleOCR'}...")
    if USE_EASYOCR:
        ocr = easyocr.Reader(['en'], gpu=True)
        print("✅ EasyOCR ready")
    else:
        ocr = PaddleOCR(lang='en')
        print("✅ PaddleOCR ready")
    
    # Detect
    print("\n🔍 Running detection...")
    results = model.track(frame, persist=False, classes=[0,1,2,3,4,5], verbose=False)
    
    vehicles = []
    plates = []
    
    if results[0].boxes:
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            if cls_id == 5:  # plate
                plates.append({"box": (x1, y1, x2, y2)})
            else:  # vehicle
                vehicles.append({
                    "cls": cls_id,
                    "box": (x1, y1, x2, y2),
                    "label": VEHICLE_CLASSES[cls_id]
                })
    
    print(f"✅ Found: {len(vehicles)} vehicles, {len(plates)} plates")
    
    # Map plates to vehicles
    print("\n🔗 Mapping plates to vehicles...")
    vehicle_plates = {}  # {veh_idx: plate_dict}
    vehicle_texts = {}   # {veh_idx: text}
    
    for plate in plates:
        px1, py1, px2, py2 = plate["box"]
        
        for idx, veh in enumerate(vehicles):
            vx1, vy1, vx2, vy2 = veh["box"]
            
            # Check 100% inside
            if px1 >= vx1 and px2 <= vx2 and py1 >= vy1 and py2 <= vy2:
                vehicle_plates[idx] = plate
                print(f"  ✅ Plate mapped to vehicle {idx+1} ({veh['label']})")
                break
    
    # Run OCR
    print("\n🔤 Running OCR on plates...")
    for idx, plate in vehicle_plates.items():
        text = run_ocr(ocr, frame, plate["box"], use_easyocr=USE_EASYOCR, save_debug=True)
        vehicle_texts[idx] = text
        
        if text:
            print(f"  ✅ Vehicle {idx+1}: '{text}'")
        else:
            print(f"  ⚠️  Vehicle {idx+1}: no text detected")
    
    # Draw results
    print("\n🎨 Drawing results...")
    result_img = frame.copy()
    
    for idx, veh in enumerate(vehicles):
        x1, y1, x2, y2 = veh["box"]
        
        # Draw vehicle box (green)
        cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        label = f"{veh['label']} #{idx+1}"
        if idx in vehicle_texts and vehicle_texts[idx]:
            label += f" [{vehicle_texts[idx]}]"
        
        cv2.putText(result_img, label, (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Draw plate box if exists
        if idx in vehicle_plates:
            px1, py1, px2, py2 = vehicle_plates[idx]["box"]
            cv2.rectangle(result_img, (px1, py1), (px2, py2), (0, 255, 0), 2)
            
            if idx in vehicle_texts and vehicle_texts[idx]:
                cv2.putText(result_img, vehicle_texts[idx], (px1, py1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # Resize if too large
    if w > 1920 or h > 1080:
        scale = min(1920/w, 1080/h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        result_img = cv2.resize(result_img, (new_w, new_h))
        print(f"🔽 Resized to {new_w}x{new_h} for display")
    
    # Show
    cv2.imshow("OCR Test Result", result_img)
    print("\n👁️  Press any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print(f"\n{'='*60}")
    print("✅ TEST COMPLETED")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    # Select image with file dialog
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    print("\n📂 Select an image file...")
    image_path = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[
            ("Image Files", "*.jpg *.jpeg *.png *.bmp"),
            ("All Files", "*.*")
        ]
    )
    root.destroy()
    
    if image_path:
        print(f"✅ Selected: {image_path}")
        test_pipeline(image_path)
    else:
        print("❌ No image selected")

"""
Test PaddleOCR Pipeline - Giống như trong video detection
Kiểm tra OCR trên biển số xe sau khi YOLO detect
"""

import cv2
import sys
import numpy as np
from pathlib import Path
from tkinter import Tk, filedialog

# Import YOLO
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully")
except ImportError as e:
    print(f"❌ Cannot import YOLO: {e}")
    sys.exit(1)

# Import PaddleOCR
try:
    from paddleocr import PaddleOCR
    print("✅ PaddleOCR imported successfully")
except ImportError as e:
    print(f"❌ Cannot import PaddleOCR: {e}")
    print("Please install: pip install paddleocr paddlepaddle")
    sys.exit(1)

def test_ocr_on_image(image_path):
    """Test OCR on image with YOLO detection pipeline"""
    
    # Initialize YOLO
    print("\n🔧 Initializing YOLO model...")
    model_path = "models/yolov8/416_vehicle_plate.pt"
    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        return
    
    try:
        model = YOLO(model_path)
        print(f"✅ YOLO model loaded: {model_path}")
    except Exception as e:
        print(f"❌ Failed to load YOLO: {e}")
        return
    
    # Initialize OCR
    print("\n🔧 Initializing PaddleOCR...")
    try:
        # Use 'en' for English characters and numbers (suitable for VN plates)
        # Vietnamese plates: 2 digits + letter + dash + 5 digits (e.g., 51F-12345)
        ocr = PaddleOCR(use_textline_orientation=True, lang='en')
        print("✅ PaddleOCR initialized (lang=en)")
    except Exception as e:
        print(f"❌ Failed to initialize PaddleOCR: {e}")
        return
    
    # Load image
    print(f"\n📷 Loading image: {image_path}")
    img = cv2.imread(image_path)
    
    if img is None:
        print(f"❌ Cannot load image: {image_path}")
        return
    
    print(f"✅ Image loaded: {img.shape[1]}x{img.shape[0]} (WxH)")
    
    # Run YOLO detection
    print("\n🚗 Running YOLO detection...")
    results = model(img, imgsz=416, conf=0.25, classes=[0, 1, 3, 4, 5], verbose=False)
    
    vehicles = []
    plates = []
    
    print("\n📊 All detections:")
    if results[0].boxes is not None:
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf_val = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            cls_name = {0: 'ô tô', 1: 'xe bus', 3: 'xe máy', 4: 'xe tải', 5: 'biển số'}.get(cls_id, f'class_{cls_id}')
            print(f"  - {cls_name}: conf={conf_val:.3f}, box=({x1},{y1},{x2},{y2})")
            
            if cls_id == 5:  # License plate
                plates.append({
                    'box': (x1, y1, x2, y2),
                    'conf': conf_val
                })
            else:  # Vehicle
                vehicles.append({
                    'cls_id': cls_id,
                    'box': (x1, y1, x2, y2),
                    'conf': conf_val
                })
    
    print(f"✅ Detected: {len(vehicles)} vehicles, {len(plates)} plates")
    
    # Draw detection results
    img_display = img.copy()
    
    # Draw vehicles
    for veh in vehicles:
        x1, y1, x2, y2 = veh['box']
        cv2.rectangle(img_display, (x1, y1), (x2, y2), (0, 255, 0), 2)
    
    # Process each plate with OCR
    if plates:
        print(f"\n🔤 Running OCR on {len(plates)} plate(s)...")
        print("-" * 70)
        
        for idx, plate in enumerate(plates):
            x1, y1, x2, y2 = plate['box']
            conf = plate['conf']
            
            # Crop plate region from ORIGINAL image
            plate_img = img[y1:y2, x1:x2]
            
            if plate_img.size == 0:
                print(f"{idx+1}. ⚠️  Empty plate crop")
                continue
            
            print(f"\n{idx+1}. Plate BBox: ({x1}, {y1}, {x2}, {y2})")
            print(f"   Plate Size: {x2-x1}x{y2-y1}")
            print(f"   Detection Conf: {conf:.3f}")
            
            # Preprocessing: Resize plate to larger size for better OCR
            plate_h, plate_w = plate_img.shape[:2]
            target_height = 200  # Increase to 200px for better OCR
            if plate_h < target_height:
                scale = target_height / plate_h
                new_w = int(plate_w * scale)
                new_h = int(plate_h * scale)
                plate_img_resized = cv2.resize(plate_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                print(f"   📏 Resized: {plate_w}x{plate_h} → {new_w}x{new_h}")
            else:
                plate_img_resized = plate_img
            
            # Try multiple preprocessing methods
            preprocessed_versions = {}
            
            # Version 1: Original resized
            preprocessed_versions['original'] = plate_img_resized
            
            # Version 2: Grayscale + Binary threshold
            gray = cv2.cvtColor(plate_img_resized, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            preprocessed_versions['binary'] = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            
            # Version 3: CLAHE enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            preprocessed_versions['clahe'] = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
            # Version 4: Bilateral filter (reduce noise, keep edges)
            bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
            preprocessed_versions['bilateral'] = cv2.cvtColor(bilateral, cv2.COLOR_GRAY2BGR)
            
            # Save all versions
            plate_crop_path = f"plate_crop_{idx+1}_original.jpg"
            cv2.imwrite(plate_crop_path, plate_img)
            print(f"   💾 Original: {plate_crop_path}")
            
            for method, img_proc in preprocessed_versions.items():
                path = f"plate_crop_{idx+1}_{method}.jpg"
                cv2.imwrite(path, img_proc)
                print(f"   💾 {method.title()}: {path}")
            
            # Run OCR on all preprocessing versions
            best_result = None
            best_conf = 0.0
            
            print(f"\n   🔤 Testing OCR with different preprocessing:")
            for method, img_proc in preprocessed_versions.items():
                try:
                    ocr_result = ocr.predict(img_proc)
                    
                    if ocr_result and len(ocr_result) > 0:
                        result_obj = ocr_result[0]
                        
                        # Get texts and scores
                        texts = []
                        scores = []
                        
                        if hasattr(result_obj, 'rec_texts'):
                            texts = result_obj.rec_texts
                        if hasattr(result_obj, 'rec_scores'):
                            scores = result_obj.rec_scores
                        
                        if texts:
                            # Combine all text
                            full_text = ' '.join(texts)
                            avg_conf = sum(scores) / len(scores) if scores else 0.0
                            
                            print(f"      [{method}] '{full_text}' (conf: {avg_conf:.3f})")
                            
                            # Keep best result
                            if avg_conf > best_conf:
                                best_conf = avg_conf
                                best_result = full_text
                        else:
                            print(f"      [{method}] No text detected")
                    else:
                        print(f"      [{method}] Empty result")
                        
                except Exception as e:
                    print(f"      [{method}] Error: {e}")
            
            # Display final result
            print()
            if best_result:
                print(f"   ✅ Best OCR Result: '{best_result}'")
                print(f"   📊 Best Confidence: {best_conf:.3f} ({best_conf*100:.1f}%)")
                
                # Draw plate and text on display image
                cv2.rectangle(img_display, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(img_display, best_result, (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            else:
                print(f"   ⚠️  All OCR methods failed - No text detected")
                cv2.rectangle(img_display, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        print("-" * 70)
    else:
        print("\n⚠️  No plates detected")
    
    # Save result
    output_path = str(Path(image_path).parent / f"{Path(image_path).stem}_pipeline_result.jpg")
    cv2.imwrite(output_path, img_display)
    print(f"\n💾 Result saved: {output_path}")
    
    # Display image
    print("\n👁️  Press any key to close the image window...")
    cv2.imshow('Detection + OCR Result', img_display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def test_ocr_on_video_frame(video_path, frame_number=100):
    """Extract a frame from video and test OCR with YOLO pipeline"""
    
    print(f"\n📹 Loading video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return
    
    # Seek to frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print(f"❌ Cannot read frame {frame_number}")
        return
    
    print(f"✅ Extracted frame {frame_number}: {frame.shape[1]}x{frame.shape[0]} (WxH)")
    
    # Save frame
    frame_path = f"test_frame_{frame_number}.jpg"
    cv2.imwrite(frame_path, frame)
    print(f"💾 Frame saved: {frame_path}")
    
    # Test OCR on frame
    test_ocr_on_image(frame_path)

if __name__ == "__main__":
    print("="*70)
    print("PaddleOCR Test Script")
    print("="*70)
    
    # Option 1: Test on existing image
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if image_path.endswith('.mp4') or image_path.endswith('.avi'):
            # Video file
            frame_num = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            test_ocr_on_video_frame(image_path, frame_num)
        else:
            # Image file
            test_ocr_on_image(image_path)
    
    # Option 2: File dialog
    else:
        print("\n📁 Opening file dialog...")
        root = Tk()
        root.withdraw()  # Hide main window
        
        file_path = filedialog.askopenfilename(
            title="Select image or video file",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                ("Video files", "*.mp4 *.avi *.mkv"),
                ("All files", "*.*")
            ],
            initialdir="D:/test adcv"
        )
        
        if file_path:
            print(f"✅ Selected: {file_path}")
            
            if file_path.lower().endswith(('.mp4', '.avi', '.mkv')):
                # Video: extract frame
                test_ocr_on_video_frame(file_path, frame_number=100)
            else:
                # Image
                test_ocr_on_image(file_path)
        else:
            print("❌ No file selected")
            
            # Default fallback
            video_path = "D:/test adcv/videotest2_30fps.mp4"
            if Path(video_path).exists():
                print(f"\n🎬 Testing with default video: {video_path}")
                test_ocr_on_video_frame(video_path, frame_number=100)
            else:
                print("\n⚠️  No default video found.")

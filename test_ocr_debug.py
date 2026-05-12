"""
Debug script to test OCR functionality with YOLO detected plate crops
"""
import cv2
import numpy as np
import sys
import os

# Ensure UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Import OCR
try:
    from paddleocr import PaddleOCR
    print("✅ PaddleOCR imported successfully")
except Exception as e:
    print(f"❌ PaddleOCR import failed: {e}")
    exit(1)

try:
    import easyocr
    print("✅ EasyOCR imported successfully")
except Exception as e:
    print(f"⚠️ EasyOCR not available: {e}")

import torch
print(f"🔧 PyTorch version: {torch.__version__}")
print(f"🔧 CUDA available: {torch.cuda.is_available()}")

# Initialize PaddleOCR with different settings
print("\n" + "="*80)
print("INITIALIZING PADDLEOCR")
print("="*80)

try:
    ocr = PaddleOCR(use_textline_orientation=True, lang='en')
    print("✅ PaddleOCR initialized")
except Exception as e:
    print(f"❌ Failed to initialize PaddleOCR: {e}")
    exit(1)

# Test with a simple image: create a synthetic license plate
print("\n" + "="*80)
print("TESTING WITH SYNTHETIC PLATE")
print("="*80)

# Create a white image
plate_img = np.ones((100, 300, 3), dtype=np.uint8) * 255

# Add black text (license plate simulation)
cv2.putText(plate_img, "29B12345", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)

# Save test image
cv2.imwrite("test_synthetic_plate.jpg", plate_img)
print("✅ Saved synthetic plate to test_synthetic_plate.jpg")

# Test 1: Recognize-only mode (det=False, rec=True)
print("\n🔍 Test 1: Recognition-only mode (det=False, rec=True)")
try:
    result = ocr.ocr(plate_img, det=False, rec=True, cls=False)
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
    if result:
        print(f"Result length: {len(result)}")
        if isinstance(result, list) and len(result) > 0:
            print(f"First element: {result[0]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Full detection + recognition
print("\n🔍 Test 2: Full mode (detection + recognition)")
try:
    result = ocr.ocr(plate_img, cls=False)
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Try with greyscale
print("\n🔍 Test 3: Greyscale version")
plate_gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
try:
    result = ocr.ocr(plate_gray, det=False, rec=True, cls=False)
    print(f"Result: {result}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Test with actual video frame (if video exists)
print("\n" + "="*80)
print("TESTING WITH ACTUAL VIDEO FRAME")
print("="*80)

# Find a video file
video_paths = [
    "sample_video.mp4",
    "test_video.mp4",
    "video.mp4",
    "configs/sample_traffic_video_config.json",  # Check if video is referenced
]

# Try to find video in configs
import json
config_dir = "configs"

if os.path.exists(config_dir):
    for config_file in os.listdir(config_dir):
        if config_file.endswith("_config.json"):
            config_path = os.path.join(config_dir, config_file)
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if "video_path" in config:
                        video_paths.append(config["video_path"])
                        print(f"Found video in {config_file}: {config['video_path']}")
            except Exception as e:
                pass

# Try each video path
video_found = False
for video_path in video_paths:
    if os.path.exists(video_path):
        print(f"\n✅ Found video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            video_found = True
            ret, frame = cap.read()
            if ret:
                print(f"✅ Read frame: {frame.shape}")
                
                # Try to crop a region (simulate a plate)
                h, w = frame.shape[:2]
                # Crop from middle of frame (where vehicles are likely)
                crop_h = min(100, h // 4)
                crop_w = min(300, w // 2)
                
                y1, x1 = h // 2 - crop_h // 2, w // 2 - crop_w // 2
                y2, x2 = y1 + crop_h, x1 + crop_w
                
                plate_crop = frame[y1:y2, x1:x2]
                cv2.imwrite("test_actual_crop.jpg", plate_crop)
                print(f"✅ Saved crop to test_actual_crop.jpg: {plate_crop.shape}")
                
                # Test OCR on actual crop
                print("\n🔍 Testing OCR on actual video crop:")
                try:
                    result = ocr.ocr(plate_crop, det=False, rec=True, cls=False)
                    print(f"Result: {result}")
                except Exception as e:
                    print(f"⚠️ Error: {e}")
                    # Try alternative
                    try:
                        result = ocr.ocr(plate_crop, cls=False)
                        print(f"Result (full mode): {result}")
                    except Exception as e2:
                        print(f"❌ Error (full mode): {e2}")
            
            cap.release()
            if video_found:
                break

if not video_found:
    print("\n⚠️ No video found for testing")

# Test 5: Check PaddleOCR internal result format
print("\n" + "="*80)
print("ANALYZING RESULT FORMAT")
print("="*80)

try:
    result = ocr.ocr(plate_img, det=False, rec=True, cls=False)
    print(f"Type of result: {type(result)}")
    print(f"Result: {result}")
    
    if result:
        print("\n📊 Result structure analysis:")
        for i, item in enumerate(result):
            print(f"  result[{i}] type: {type(item)}, value: {item}")
            if isinstance(item, list):
                for j, subitem in enumerate(item):
                    print(f"    [{i}][{j}] type: {type(subitem)}, value: {subitem}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*80)
print("TESTING EASYOCR")
print("="*80)

try:
    import easyocr
    print("🔄 Initializing EasyOCR...")
    reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available(), verbose=False)
    print("✅ EasyOCR initialized")
    
    print("\n🔍 Testing EasyOCR on synthetic plate:")
    result = reader.readtext(plate_img, detail=1, paragraph=False)
    print(f"Result: {result}")
    
    if result:
        print("\n📊 EasyOCR result structure:")
        for i, item in enumerate(result):
            print(f"  [{i}] {item}")
            
except Exception as e:
    print(f"⚠️ EasyOCR test failed: {e}")

print("\n" + "="*80)
print("DEBUG COMPLETE")
print("="*80)

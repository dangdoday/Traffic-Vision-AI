"""
Test updated OCR with EasyOCR as primary method
"""
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import easyocr
    print("✅ EasyOCR imported")
except Exception as e:
    print(f"❌ EasyOCR import failed: {e}")
    exit(1)

import torch
print(f"🔧 PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")

# Initialize EasyOCR
print("\n🔄 Initializing EasyOCR...")
reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available(), verbose=False)
print("✅ EasyOCR initialized")

# Create synthetic test plate
plate_img = np.ones((100, 300, 3), dtype=np.uint8) * 255
cv2.putText(plate_img, "29B12345", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
cv2.imwrite("test_plate_synthetic.jpg", plate_img)

# Test EasyOCR
print("\n🔍 Test 1: Synthetic plate")
result = reader.readtext(plate_img, detail=1, paragraph=False, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
print(f"Result: {result}")

# Extract text
texts = []
for item in result:
    if isinstance(item, (list, tuple)) and len(item) >= 3:
        text = str(item[1]).strip()
        conf = float(item[2])
        if text and conf >= 0.2:
            texts.append(text)
            print(f"  - '{text}' (conf: {conf:.3f})")

# Normalize
import re
normalized = re.sub(r'[^A-Z0-9]', '', "".join(texts).upper())
print(f"✅ Final text: {normalized}")

# Test with actual video frame
print("\n" + "="*80)
print("Test 2: Actual video frame crop")
print("="*80)

import os
import json

config_dir = "configs"
video_found = False

for config_file in os.listdir(config_dir):
    if config_file.endswith("_config.json") and "Recording" in config_file:
        config_path = os.path.join(config_dir, config_file)
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                video_path = config.get("video_path", "")
                if os.path.exists(video_path):
                    print(f"✅ Found video: {video_path}")
                    cap = cv2.VideoCapture(video_path)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            h, w = frame.shape[:2]
                            # Crop middle region
                            crop_h = min(100, h // 4)
                            crop_w = min(300, w // 2)
                            y1, x1 = h // 2 - crop_h // 2, w // 2 - crop_w // 2
                            y2, x2 = y1 + crop_h, x1 + crop_w
                            
                            plate_crop = frame[y1:y2, x1:x2]
                            cv2.imwrite("test_plate_actual.jpg", plate_crop)
                            print(f"✅ Crop saved: {plate_crop.shape}")
                            
                            # Test OCR
                            result = reader.readtext(plate_crop, detail=1, paragraph=False, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                            print(f"\n🔍 OCR result on actual frame crop:")
                            
                            texts = []
                            for item in result:
                                if isinstance(item, (list, tuple)) and len(item) >= 3:
                                    text = str(item[1]).strip()
                                    conf = float(item[2])
                                    if text and conf >= 0.2:
                                        texts.append(text)
                                        print(f"  - '{text}' (conf: {conf:.3f})")
                            
                            if texts:
                                normalized = re.sub(r'[^A-Z0-9]', '', "".join(texts).upper())
                                print(f"✅ Extracted: {normalized}")
                            else:
                                print(f"⚠️ No text detected (confidence >= 0.2)")
                                
                                # Show all detections
                                print(f"\n📊 All detections (any confidence):")
                                for item in result:
                                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                                        text = str(item[1]).strip()
                                        conf = float(item[2])
                                        print(f"  - '{text}' (conf: {conf:.3f})")
                            
                            video_found = True
                        cap.release()
                        if video_found:
                            break
        except Exception as e:
            pass

if not video_found:
    print("⚠️ No suitable video found for testing")

print("\n" + "="*80)
print("✅ Test complete!")
print("="*80)

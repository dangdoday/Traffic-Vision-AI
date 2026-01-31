"""plate_ocr_pipeline.py

Run detection → crop plate → perspective-warp to frontal → OCR

Usage:
  python scripts/plate_ocr_pipeline.py --image path/to/img.jpg
"""
import os
import sys
import argparse
import cv2
import numpy as np

# Make project root importable so we can import src.tools
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ultralytics import YOLO

try:
    from easyocr import Reader as EasyReader
    HAVE_EASYOCR = True
except Exception:
    HAVE_EASYOCR = False

try:
    from paddleocr import PaddleOCR
    HAVE_PADDLE = True
except Exception:
    HAVE_PADDLE = False

from src.tools.plate_warp import warp_minarearect_from_black_regions


def preprocess_plate(img):
    h, w = img.shape[:2]
    if h < 100:
        scale = 100 / h
        img = cv2.resize(img, (int(w * scale), 100), interpolation=cv2.INTER_CUBIC)

    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    img = clahe.apply(img)
    img = cv2.bilateralFilter(img, 5, 75, 75)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    img = cv2.filter2D(img, -1, kernel)
    return img


def ocr_on_image(ocr, img, use_easy=False):
    """Run OCR on a plate image (numpy BGR or grayscale). Returns text."""
    try:
        processed = preprocess_plate(img)
        if use_easy:
            if len(processed.shape) == 2:
                processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            else:
                processed_bgr = processed
            result = ocr.readtext(processed_bgr, detail=0, allowlist='0123456789ABCDEFGHKLMNPSTUVXYZ-.')
            text = "".join(result).replace(" ", "")
            return text
        else:
            if len(processed.shape) == 2:
                processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            else:
                processed_bgr = processed
            result = ocr.ocr(processed_bgr, cls=False)
            if result and len(result) > 0 and result[0]:
                texts = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                            text = str(text_info[0]).strip()
                            conf = float(text_info[1])
                            if conf > 0.5:
                                texts.append(text)
                if texts:
                    return "".join(texts).replace(" ", "").replace(".", "")
            return ""
    except Exception as e:
        print(f"    ❌ OCR error: {e}")
        return ""


def pad_box(box, pad_ratio=0.15, img_w=None, img_h=None):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    pad_w = int(w * pad_ratio)
    pad_h = int(h * pad_ratio)
    nx1 = max(0, x1 - pad_w)
    ny1 = max(0, y1 - pad_h)
    nx2 = min(img_w, x2 + pad_w) if img_w is not None else x2 + pad_w
    ny2 = min(img_h, y2 + pad_h) if img_h is not None else y2 + pad_h
    return int(nx1), int(ny1), int(nx2), int(ny2)


def run_pipeline(image_path, model_path="models/yolov8/416_vehicle_plate.pt", save_debug=True):
    print(f"Image: {image_path}")
    frame = cv2.imread(image_path)
    if frame is None:
        print("❌ Cannot read image")
        return

    h, w = frame.shape[:2]

    model = YOLO(model_path)
    print("✅ YOLO loaded")

    use_easy = HAVE_EASYOCR
    if use_easy:
        ocr = EasyReader(['en'], gpu=False)
        print("✅ EasyOCR ready")
    elif HAVE_PADDLE:
        ocr = PaddleOCR(lang='en')
        print("✅ PaddleOCR ready")
    else:
        print("❌ No OCR available (install easyocr or paddleocr)")
        return

    # Detect
    print("🔍 Running detection...")
    results = model.track(frame, persist=False, classes=[5], verbose=False)

    plates = []
    if results and len(results) > 0 and results[0].boxes:
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id != 5:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            plates.append((x1, y1, x2, y2))

    print(f"✅ Found {len(plates)} plate(s)")

    results_texts = []
    debug_dir = "ocr_debug"
    os.makedirs(debug_dir, exist_ok=True)

    for i, pb in enumerate(plates):
        px1, py1, px2, py2 = pad_box(pb, pad_ratio=0.2, img_w=w, img_h=h)
        crop = frame[py1:py2, px1:px2].copy()
        if crop.size == 0:
            results_texts.append("")
            continue

        # Try warp
        warped = None
        try:
            warped_img, up_clean, mask_used, box = warp_minarearect_from_black_regions(crop, upscale=4, remove_blue_box=True)
            # warped_img is upscaled; OCR preprocess will handle resizing
            warped = warped_img
            if save_debug:
                cv2.imwrite(os.path.join(debug_dir, f"plate_{i}_warped.png"), warped)
                cv2.imwrite(os.path.join(debug_dir, f"plate_{i}_up.png"), up_clean)
                cv2.imwrite(os.path.join(debug_dir, f"plate_{i}_mask.png"), mask_used)
        except Exception as e:
            print(f"  ⚠️  Warp failed for plate {i}: {e} — falling back to axis crop")
            warped = crop

        text = ocr_on_image(ocr, warped, use_easy=use_easy)
        results_texts.append(text)
        print(f"  Plate {i+1}: '{text}'")

    # Draw result
    out = frame.copy()
    for i, pb in enumerate(plates):
        x1, y1, x2, y2 = pb
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = results_texts[i] if i < len(results_texts) else ""
        if label:
            cv2.putText(out, label, (x1, max(15, y1-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

    out_path = "ocr_pipeline_result.jpg"
    cv2.imwrite(out_path, out)
    print(f"✅ Result saved: {out_path}")
    if save_debug:
        print(f"✅ Debug images saved to: {debug_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--model", default="models/yolov8/416_vehicle_plate.pt", help="YOLO model path")
    args = parser.parse_args()
    run_pipeline(args.image, model_path=args.model)


if __name__ == "__main__":
    main()

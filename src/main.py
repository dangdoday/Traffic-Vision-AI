import os
import sys

# ============================================================
# CRITICAL: Import YOLO TRƯỚC PyQt để tránh lỗi DLL
# ============================================================
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully before PyQt")
    YOLO_AVAILABLE = True
except Exception as e:
    print(f"❌ YOLO import failed: {e}")
    YOLO_AVAILABLE = False

from PyQt5.QtWidgets import QApplication


# Ensure UTF-8 output to avoid console encode errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import main từ integrated_main.py
from integrated_main import main

if __name__ == "__main__":
    main()

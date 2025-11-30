"""
Main Entry Point for Traffic Vision AI - Modular Version
Uses modularized components while maintaining backward compatibility
"""

import sys
import os

# Add project root to path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# CRITICAL: Import YOLO BEFORE PyQt to avoid DLL conflicts
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully before PyQt")
    YOLO_AVAILABLE = True
except Exception as e:
    print(f"❌ YOLO import failed: {e}")
    YOLO_AVAILABLE = False

# Now safe to import integrated_main
from integrated_main import main

if __name__ == "__main__":
    print("🚀 Starting Traffic Vision AI - Modular Version")
    print("📦 Using modularized components:")
    print("   - core/violation_checker.py")
    print("   - core/traffic_light_classifier.py")
    print("   - app/state/app_state.py")
    print("   - utils/drawing_utils.py")
    print("   - utils/geometry_utils.py")
    main()

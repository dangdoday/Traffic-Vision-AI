"""
Traffic Vision AI - Compact Version
Kế thừa 100% tính năng từ integrated_main.py nhưng code ngắn gọn

Strategy: Import và extend MainWindow thay vì viết lại
"""

import sys

# CRITICAL: Import YOLO BEFORE PyQt
try:
    from ultralytics import YOLO
    print("✅ YOLO imported successfully before PyQt")
    YOLO_AVAILABLE = True
except Exception as e:
    print(f"❌ YOLO import failed: {e}")
    YOLO_AVAILABLE = False

from PyQt5.QtWidgets import QApplication

# Import MainWindow từ integrated_main (đã có đầy đủ tính năng)
from integrated_main import MainWindow

# Import các modules modular để có thể customize sau này
from core.violation_checker import check_tl_violation
from core.traffic_light_classifier import classify_tl_color
from utils.drawing_utils import draw_lanes, draw_stop_line
from utils.geometry_utils import point_in_polygon


class CompactMainWindow(MainWindow):
    """
    Kế thừa 100% tính năng từ MainWindow (integrated_main.py)
    
    Lợi ích:
    - Đầy đủ tính năng (menu, shortcuts, ROI editor, etc.)
    - Code ngắn gọn (chỉ ~50 dòng)
    - Có thể override/customize bất kỳ method nào
    - Sử dụng modules modular
    """
    
    def __init__(self):
        # Gọi __init__ của MainWindow (integrated_main)
        # Tất cả UI, thread, model đều được setup tự động
        super().__init__()
        
        # Customize window title
        self.setWindowTitle("🚀 Traffic Vision AI - Compact Modular Edition")

    
    # Ví dụ: Override method nếu muốn customize
    # def start_detection(self):
    #     """Override để thêm custom logic"""
    #     print("🚀 Custom detection logic...")
    #     super().start_detection()  # Gọi logic gốc
    
    # def update_tl_colors(self, frame):
    #     """Override để dùng module classifier"""
    #     # Custom implementation using classify_tl_color module
    #     super().update_tl_colors(frame)  # Hoặc gọi logic gốc


def main():
    """Entry point"""
    app = QApplication(sys.argv)
    
    # Tạo window - tự động có đầy đủ tính năng
    window = CompactMainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

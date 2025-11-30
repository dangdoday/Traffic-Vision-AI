"""
Reference Vector Calibration Tool
Dùng để xác định hướng "đi thẳng" của đường (reference vector)
cho camera bị nghiêng
"""
import cv2
import json
import numpy as np
import math
from pathlib import Path


class ReferenceVectorCalibrator:
    """
    Tool để người dùng vẽ reference vector bằng cách click 2 điểm
    trên làn đường đi thẳng
    """
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.frame = None
        self.original_frame = None
        
        self.point1 = None
        self.point2 = None
        self.reference_vector = None
        self.reference_angle = None
    
    def load_first_frame(self) -> bool:
        """Load frame đầu từ video"""
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("❌ Không thể đọc video!")
            return False
        
        self.frame = frame.copy()
        self.original_frame = frame.copy()
        print("✅ Đã load frame từ video")
        return True
    
    def mouse_callback(self, event, x, y, flags, param):
        """Xử lý click chuột"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.point1 is None:
                # Điểm đầu
                self.point1 = (x, y)
                print(f"📍 Điểm 1: ({x}, {y})")
                self.redraw()
            elif self.point2 is None:
                # Điểm cuối
                self.point2 = (x, y)
                print(f"📍 Điểm 2: ({x}, {y})")
                self.calculate_vector()
                self.redraw()
    
    def calculate_vector(self):
        """Tính reference vector và góc"""
        if self.point1 is None or self.point2 is None:
            return
        
        dx = self.point2[0] - self.point1[0]
        dy = self.point2[1] - self.point1[1]
        
        # Normalize
        length = math.sqrt(dx**2 + dy**2)
        if length > 0:
            self.reference_vector = (dx / length, dy / length)
        
        # Tính góc (degrees)
        self.reference_angle = math.degrees(math.atan2(dy, dx))
        
        print(f"\n✅ Reference Vector Calculated:")
        print(f"   Vector: ({dx:.1f}, {dy:.1f})")
        print(f"   Normalized: ({self.reference_vector[0]:.3f}, {self.reference_vector[1]:.3f})")
        print(f"   Angle: {self.reference_angle:.2f}°")
        print(f"   Length: {length:.1f} pixels")
    
    def redraw(self):
        """Vẽ lại frame"""
        self.frame = self.original_frame.copy()
        
        # Vẽ điểm 1
        if self.point1:
            cv2.circle(self.frame, self.point1, 8, (0, 255, 0), -1)
            cv2.putText(self.frame, "P1 (Start)", (self.point1[0] + 10, self.point1[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Vẽ điểm 2 và vector
        if self.point2:
            cv2.circle(self.frame, self.point2, 8, (0, 0, 255), -1)
            cv2.putText(self.frame, "P2 (End)", (self.point2[0] + 10, self.point2[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Vẽ mũi tên (vector)
            cv2.arrowedLine(self.frame, self.point1, self.point2, (255, 0, 255), 4, tipLength=0.05)
            
            # Vẽ thông tin vector
            if self.reference_vector and self.reference_angle is not None:
                mid_x = (self.point1[0] + self.point2[0]) // 2
                mid_y = (self.point1[1] + self.point2[1]) // 2
                
                info_text = f"Angle: {self.reference_angle:.1f}"
                cv2.putText(self.frame, info_text, (mid_x - 50, mid_y - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Hướng dẫn
        instructions = [
            "Click 2 points on STRAIGHT lane:",
            "1. Start of straight section",
            "2. End of straight section",
            "",
            "R: Reset | S: Save | Q: Quit"
        ]
        
        y = 30
        for text in instructions:
            color = (255, 255, 255) if text else (200, 200, 200)
            cv2.putText(self.frame, text, (10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y += 30
        
        cv2.imshow('Reference Vector Calibrator', self.frame)
    
    def reset(self):
        """Reset các điểm"""
        self.point1 = None
        self.point2 = None
        self.reference_vector = None
        self.reference_angle = None
        print("\n🔄 Reset - click 2 điểm mới")
        self.redraw()
    
    def save(self, output_path: str = None):
        """Lưu reference vector ra JSON"""
        if self.reference_vector is None:
            print("⚠️  Chưa có reference vector để lưu!")
            return
        
        if output_path is None:
            video_dir = Path(self.video_path).parent
            output_path = video_dir / "reference_vector.json"
        
        data = {
            'video': str(Path(self.video_path).name),
            'frame_shape': self.original_frame.shape[:2],
            'point1': self.point1,
            'point2': self.point2,
            'reference_vector': {
                'x': self.reference_vector[0],
                'y': self.reference_vector[1]
            },
            'reference_angle': self.reference_angle,
            'usage': 'analyzer.set_reference_vector_from_points(point1, point2)'
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Đã lưu reference vector vào: {output_path}")
        print(f"\nSử dụng trong code:")
        print(f"  analyzer.set_reference_vector_from_points({self.point1}, {self.point2})")
        print(f"  # hoặc")
        print(f"  analyzer.set_reference_vector_from_angle({self.reference_angle:.2f})")
    
    def run(self):
        """Chạy calibrator"""
        if not self.load_first_frame():
            return
        
        cv2.namedWindow('Reference Vector Calibrator')
        cv2.setMouseCallback('Reference Vector Calibrator', self.mouse_callback)
        
        print("\n" + "="*70)
        print("🧭 REFERENCE VECTOR CALIBRATOR - Xác định hướng đi thẳng của đường")
        print("="*70)
        print("\nHƯỚNG DẪN:")
        print("  1. Click điểm ĐẦU của đoạn đường đi thẳng")
        print("  2. Click điểm CUỐI của đoạn đường đi thẳng")
        print("     (2 điểm trên cùng làn đường, cách nhau càng xa càng tốt)")
        print("\nPHÍM TẮT:")
        print("  R: Reset (vẽ lại)")
        print("  S: Save to JSON")
        print("  Q: Quit")
        print("="*70 + "\n")
        
        self.redraw()
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("👋 Thoát calibrator")
                break
            
            elif key == ord('r'):
                self.reset()
            
            elif key == ord('s'):
                self.save()
        
        cv2.destroyAllWindows()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Reference Vector Calibrator')
    parser.add_argument('--video', type=str, required=True, help='Đường dẫn đến video')
    args = parser.parse_args()
    
    calibrator = ReferenceVectorCalibrator(args.video)
    calibrator.run()


if __name__ == '__main__':
    main()

"""
ROI Direction Editor - Tool vẽ ROI thủ công cho nhận diện hướng di chuyển
Sử dụng: python roi_direction_editor.py --video <path_to_video>
"""
import cv2
import json
import argparse
import numpy as np
from pathlib import Path


class ROIDirectionEditor:
    """Tool vẽ ROI và gán nhãn hướng (left/right/straight)"""
    
    COLORS = {
        'left': (0, 0, 255),      # Đỏ - Rẽ trái
        'right': (0, 165, 255),   # Vàng - Rẽ phải
        'straight': (0, 255, 0),  # Xanh - Đi thẳng
        'unknown': (128, 128, 128) # Xám - Chưa xác định
    }
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.frame = None
        self.original_frame = None
        
        # ROI data
        self.rois = []
        self.current_roi = {
            'name': '',
            'points': [],
            'direction': 'straight'
        }
        self.is_drawing = False
        
        # UI state
        self.selected_direction = 'straight'
        
    def load_first_frame(self) -> bool:
        """Load frame đầu tiên từ video"""
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
        """Xử lý sự kiện chuột"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Thêm điểm vào ROI hiện tại
            self.current_roi['points'].append([x, y])
            print(f"📍 Điểm {len(self.current_roi['points'])}: ({x}, {y})")
            self.redraw()
            
        elif event == cv2.EVENT_MOUSEMOVE and self.current_roi['points']:
            # Hiển thị đường nét từ điểm cuối đến con trỏ
            temp_frame = self.frame.copy()
            last_point = tuple(self.current_roi['points'][-1])
            cv2.line(temp_frame, last_point, (x, y), 
                    self.COLORS[self.selected_direction], 2)
            cv2.imshow('ROI Direction Editor', temp_frame)
    
    def redraw(self):
        """Vẽ lại tất cả ROIs"""
        self.frame = self.original_frame.copy()
        
        # Vẽ các ROI đã hoàn thành
        for roi in self.rois:
            pts = np.array(roi['points'], dtype=np.int32)
            color = self.COLORS.get(roi['direction'], self.COLORS['unknown'])
            
            # Vẽ polygon với độ trong suốt
            overlay = self.frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.3, self.frame, 0.7, 0, self.frame)
            
            # Vẽ viền
            cv2.polylines(self.frame, [pts], True, color, 3)
            
            # Vẽ tên ROI
            center = np.mean(pts, axis=0).astype(int)
            cv2.putText(self.frame, f"{roi['name']} ({roi['direction']})", 
                       tuple(center), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.8, (255, 255, 255), 2)
        
        # Vẽ ROI đang vẽ
        if self.current_roi['points']:
            pts = np.array(self.current_roi['points'], dtype=np.int32)
            color = self.COLORS[self.selected_direction]
            
            # Vẽ các điểm
            for pt in self.current_roi['points']:
                cv2.circle(self.frame, tuple(pt), 5, color, -1)
            
            # Vẽ đường nối
            if len(self.current_roi['points']) > 1:
                cv2.polylines(self.frame, [pts], False, color, 2)
        
        # Vẽ hướng dẫn
        self.draw_instructions()
        cv2.imshow('ROI Direction Editor', self.frame)
    
    def draw_instructions(self):
        """Vẽ hướng dẫn sử dụng"""
        instructions = [
            f"Direction: {self.selected_direction.upper()}",
            "Click: Add point | N: Finish ROI | S: Save",
            "1: LEFT | 2: STRAIGHT | 3: RIGHT",
            "D: Delete last ROI | Q: Quit",
            f"ROIs: {len(self.rois)} | Points: {len(self.current_roi['points'])}"
        ]
        
        y = 30
        for i, text in enumerate(instructions):
            color = self.COLORS[self.selected_direction] if i == 0 else (255, 255, 255)
            cv2.putText(self.frame, text, (10, y + i * 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    def finish_current_roi(self):
        """Kết thúc ROI hiện tại"""
        if len(self.current_roi['points']) < 3:
            print("⚠️  ROI cần ít nhất 3 điểm!")
            return
        
        # Gán tên tự động
        roi_num = len(self.rois) + 1
        self.current_roi['name'] = f"roi_{roi_num}"
        self.current_roi['direction'] = self.selected_direction
        
        # Lưu ROI
        self.rois.append(self.current_roi.copy())
        print(f"✅ Hoàn thành ROI #{roi_num} - {self.selected_direction} ({len(self.current_roi['points'])} points)")
        
        # Reset
        self.current_roi = {
            'name': '',
            'points': [],
            'direction': 'straight'
        }
        self.redraw()
    
    def delete_last_roi(self):
        """Xóa ROI cuối cùng"""
        if self.rois:
            deleted = self.rois.pop()
            print(f"🗑️  Đã xóa {deleted['name']}")
            self.redraw()
        else:
            print("⚠️  Không có ROI nào để xóa!")
    
    def save_rois(self, output_path: str = None):
        """Lưu ROIs ra file JSON"""
        if not self.rois:
            print("⚠️  Không có ROI nào để lưu!")
            return
        
        if output_path is None:
            video_dir = Path(self.video_path).parent
            output_path = video_dir / "rois_direction.json"
        
        data = {
            'video': str(Path(self.video_path).name),
            'frame_shape': self.original_frame.shape[:2],  # (height, width)
            'rois': self.rois
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Đã lưu {len(self.rois)} ROIs vào: {output_path}")
        print(f"   - LEFT: {sum(1 for r in self.rois if r['direction'] == 'left')}")
        print(f"   - STRAIGHT: {sum(1 for r in self.rois if r['direction'] == 'straight')}")
        print(f"   - RIGHT: {sum(1 for r in self.rois if r['direction'] == 'right')}")
    
    def run(self):
        """Chạy editor"""
        if not self.load_first_frame():
            return
        
        cv2.namedWindow('ROI Direction Editor')
        cv2.setMouseCallback('ROI Direction Editor', self.mouse_callback)
        
        print("\n" + "="*60)
        print("🎨 ROI DIRECTION EDITOR")
        print("="*60)
        print("HƯỚNG DẪN:")
        print("  • Click chuột: Thêm điểm vào ROI")
        print("  • N: Kết thúc ROI hiện tại")
        print("  • 1: Chọn hướng RẼ TRÁI (đỏ)")
        print("  • 2: Chọn hướng ĐI THẲNG (xanh)")
        print("  • 3: Chọn hướng RẼ PHẢI (vàng)")
        print("  • D: Xóa ROI cuối cùng")
        print("  • S: Lưu tất cả ROIs")
        print("  • Q: Thoát")
        print("="*60 + "\n")
        
        self.redraw()
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("👋 Thoát editor")
                break
            
            elif key == ord('n'):
                self.finish_current_roi()
            
            elif key == ord('s'):
                self.save_rois()
            
            elif key == ord('d'):
                self.delete_last_roi()
            
            elif key == ord('1'):
                self.selected_direction = 'left'
                print("🔴 Chọn: RẼ TRÁI")
                self.redraw()
            
            elif key == ord('2'):
                self.selected_direction = 'straight'
                print("🟢 Chọn: ĐI THẲNG")
                self.redraw()
            
            elif key == ord('3'):
                self.selected_direction = 'right'
                print("🟡 Chọn: RẼ PHẢI")
                self.redraw()
        
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description='ROI Direction Editor')
    parser.add_argument('--video', type=str, required=True, help='Đường dẫn đến video')
    args = parser.parse_args()
    
    editor = ROIDirectionEditor(args.video)
    editor.run()


if __name__ == '__main__':
    main()

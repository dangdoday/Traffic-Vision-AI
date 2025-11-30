"""
Traffic Light Manager - Quản lý đèn giao thông và phát hiện màu
"""
from typing import List, Tuple, Optional, Dict
import cv2
import numpy as np


class TrafficLightManager:
    """Quản lý ROIs đèn giao thông và phát hiện màu sắc"""
    
    # Định nghĩa loại đèn
    TL_TYPES = ['tròn', 'rẽ trái', 'đi thẳng', 'rẽ phải']
    
    def __init__(self):
        # List các ROI: [(x1, y1, x2, y2, tl_type), ...]
        self.tl_rois: List[Tuple[int, int, int, int, str]] = []
    
    def add_roi(self, x1: int, y1: int, x2: int, y2: int, tl_type: str):
        """Thêm ROI đèn giao thông"""
        if tl_type not in self.TL_TYPES:
            raise ValueError(f"Invalid TL type: {tl_type}. Must be one of {self.TL_TYPES}")
        
        self.tl_rois.append((x1, y1, x2, y2, tl_type))
    
    def remove_roi(self, index: int):
        """Xóa ROI theo index"""
        if 0 <= index < len(self.tl_rois):
            self.tl_rois.pop(index)
    
    def clear_rois(self):
        """Xóa tất cả ROIs"""
        self.tl_rois.clear()
    
    def get_rois(self) -> List[Tuple[int, int, int, int, str]]:
        """Lấy danh sách ROIs"""
        return self.tl_rois.copy()
    
    def has_rois(self) -> bool:
        """Kiểm tra có ROI nào không"""
        return len(self.tl_rois) > 0
    
    def detect_colors(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, str, str]]:
        """
        Phát hiện màu sắc các đèn giao thông trong frame
        
        Args:
            frame: Frame BGR từ OpenCV
        
        Returns:
            List[(x1, y1, x2, y2, tl_type, color), ...]
            color: 'do', 'xanh', 'vang', 'unknown'
        """
        results = []
        
        for roi in self.tl_rois:
            x1, y1, x2, y2, tl_type = roi
            
            # Crop ROI
            roi_img = frame[y1:y2, x1:x2]
            
            if roi_img.size == 0:
                results.append((x1, y1, x2, y2, tl_type, 'unknown'))
                continue
            
            # Phát hiện màu
            color = self._detect_traffic_light_color(roi_img)
            results.append((x1, y1, x2, y2, tl_type, color))
        
        return results
    
    def _detect_traffic_light_color(self, roi_img: np.ndarray) -> str:
        """
        Phát hiện màu đèn giao thông trong ROI
        
        Args:
            roi_img: Ảnh ROI (BGR)
        
        Returns:
            'do', 'vang', 'xanh', hoặc 'unknown'
        """
        if roi_img.size == 0:
            return 'unknown'
        
        # Chuyển sang HSV
        hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        
        # Định nghĩa range màu trong HSV
        # Đỏ (Red) - 2 khoảng do Hue wrap around
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        # Vàng (Yellow)
        lower_yellow = np.array([15, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        
        # Xanh lá (Green)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([90, 255, 255])
        
        # Tạo masks
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        
        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # Đếm số pixel mỗi màu
        red_pixels = cv2.countNonZero(mask_red)
        yellow_pixels = cv2.countNonZero(mask_yellow)
        green_pixels = cv2.countNonZero(mask_green)
        
        # Tính tỷ lệ phần trăm
        total_pixels = roi_img.shape[0] * roi_img.shape[1]
        red_ratio = red_pixels / total_pixels
        yellow_ratio = yellow_pixels / total_pixels
        green_ratio = green_pixels / total_pixels
        
        # Threshold để xác định màu (có thể điều chỉnh)
        threshold = 0.05  # 5% diện tích
        
        # Tìm màu chiếm ưu thế
        max_ratio = max(red_ratio, yellow_ratio, green_ratio)
        
        if max_ratio < threshold:
            return 'unknown'
        
        if red_ratio == max_ratio:
            return 'do'
        elif yellow_ratio == max_ratio:
            return 'vang'
        elif green_ratio == max_ratio:
            return 'xanh'
        
        return 'unknown'
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê về đèn giao thông"""
        type_counts = {}
        for roi in self.tl_rois:
            tl_type = roi[4]
            type_counts[tl_type] = type_counts.get(tl_type, 0) + 1
        
        return {
            'total_rois': len(self.tl_rois),
            'types': type_counts
        }

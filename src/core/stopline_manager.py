"""
Stop Line Manager - Quản lý vạch dừng
"""
from typing import Optional, Tuple, List
import numpy as np


class StopLineManager:
    """Quản lý vạch dừng và kiểm tra xe qua vạch"""
    
    def __init__(self):
        self.stop_line: Optional[Tuple[int, int, int, int]] = None
    
    def set_stop_line(self, x1: int, y1: int, x2: int, y2: int):
        """Đặt vạch dừng"""
        self.stop_line = (x1, y1, x2, y2)
    
    def has_stop_line(self) -> bool:
        """Kiểm tra đã có vạch dừng chưa"""
        return self.stop_line is not None
    
    def get_stop_line(self) -> Optional[Tuple[int, int, int, int]]:
        """Lấy vạch dừng"""
        return self.stop_line
    
    def is_vehicle_on_stop_line(
        self, 
        bbox: Tuple[int, int, int, int], 
        threshold: float = 10.0
    ) -> bool:
        """
        Kiểm tra xe có đang ở trên vạch dừng không
        
        Args:
            bbox: (x1, y1, x2, y2) - bounding box của xe
            threshold: Khoảng cách tối đa để coi là "trên vạch"
        
        Returns:
            True nếu xe trên vạch
        """
        if not self.has_stop_line():
            return False
        
        x1, y1, x2, y2 = bbox
        
        # Lấy điểm dưới giữa của bbox (bottom center)
        vehicle_bottom_x = (x1 + x2) / 2
        vehicle_bottom_y = y2
        
        # Tính khoảng cách từ điểm dưới xe đến vạch dừng
        distance = self._point_to_line_distance(
            vehicle_bottom_x, 
            vehicle_bottom_y,
            self.stop_line[0], self.stop_line[1],
            self.stop_line[2], self.stop_line[3]
        )
        
        return distance < threshold
    
    def has_vehicle_crossed(
        self,
        bbox: Tuple[int, int, int, int]
    ) -> bool:
        """
        Kiểm tra xe đã vượt qua vạch dừng chưa
        
        Args:
            bbox: (x1, y1, x2, y2) - bounding box của xe
        
        Returns:
            True nếu xe đã qua vạch
        """
        if not self.has_stop_line():
            return False
        
        x1, y1, x2, y2 = bbox
        
        # Lấy điểm dưới giữa của bbox
        vehicle_bottom_x = (x1 + x2) / 2
        vehicle_bottom_y = y2
        
        # Kiểm tra xe có ở phía sau vạch dừng không
        # (giả sử xe di chuyển từ trên xuống dưới)
        line_x1, line_y1, line_x2, line_y2 = self.stop_line
        
        # Tính y trung bình của vạch dừng
        line_y_avg = (line_y1 + line_y2) / 2
        
        # Xe đã qua nếu vehicle_bottom_y > line_y_avg
        return vehicle_bottom_y > line_y_avg
    
    def _point_to_line_distance(
        self, 
        px: float, py: float,
        x1: float, y1: float, 
        x2: float, y2: float
    ) -> float:
        """
        Tính khoảng cách từ điểm (px, py) đến đoạn thẳng (x1,y1)-(x2,y2)
        
        Returns:
            Khoảng cách (pixel)
        """
        # Vector của đoạn thẳng
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Đoạn thẳng suy biến thành điểm
            return np.sqrt((px - x1)**2 + (py - y1)**2)
        
        # Tính projection parameter t
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Điểm gần nhất trên đoạn thẳng
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        
        # Khoảng cách
        distance = np.sqrt((px - nearest_x)**2 + (py - nearest_y)**2)
        return distance
    
    def clear(self):
        """Xóa vạch dừng"""
        self.stop_line = None

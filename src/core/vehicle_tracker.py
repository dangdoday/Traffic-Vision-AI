"""
Vehicle Tracker - Theo dõi vị trí và hướng di chuyển của phương tiện
"""
import time
import math
from typing import Dict, List, Tuple, Optional


class VehicleTracker:
    """Quản lý tracking và direction detection cho vehicles"""
    
    def __init__(self, time_window: float = 2.0, min_distance: float = 20.0, ref_angle: Optional[float] = None):
        """
        Args:
            time_window: Khoảng thời gian (giây) để tính vector (mặc định 2.0s)
            min_distance: Khoảng cách tối thiểu (pixels) để xác định hướng
            ref_angle: Góc tham chiếu cho hướng đi thẳng (degrees, -180 to 180)
                      None = auto-detect dựa trên góc 90° (xuống dưới)
        """
        self.positions: Dict[int, List[Tuple[int, int, float]]] = {}
        self.directions: Dict[int, str] = {}
        self.stopline_start_positions: Dict[int, Tuple[int, int, float]] = {}  # Điểm bắt đầu khi qua stopline
        self.time_window = time_window  # 2 giây
        self.min_distance = min_distance  # 20 pixels
        self.ref_angle = ref_angle if ref_angle is not None else 90.0  # Default: 90° = xuống dưới
    
    def mark_stopline_crossing(self, track_id: int, x: int, y: int):
        """Đánh dấu điểm bắt đầu khi xe vừa qua stopline"""
        current_time = time.time()
        self.stopline_start_positions[track_id] = (x, y, current_time)
        print(f"📍 Vehicle {track_id} crossed stopline at ({x}, {y}) t={current_time:.2f}")
    
    def update_position(self, track_id: int, x: int, y: int) -> str:
        """Cập nhật vị trí và tính hướng di chuyển"""
        current_time = time.time()
        
        if track_id not in self.positions:
            self.positions[track_id] = []
        
        # Thêm vị trí mới
        self.positions[track_id].append((x, y, current_time))
        
        # Xóa các vị trí cũ hơn time_window
        cutoff_time = current_time - self.time_window
        self.positions[track_id] = [
            pos for pos in self.positions[track_id] 
            if pos[2] >= cutoff_time
        ]
        
        # Tính direction
        direction = self._calculate_direction(track_id)
        self.directions[track_id] = direction
        
        return direction
    
    def _calculate_direction(self, track_id: int) -> str:
        """Tính toán hướng di chuyển dựa trên time window"""
        if track_id not in self.positions:
            return 'unknown'
        
        positions = self.positions[track_id]
        
        # Cần ít nhất 1 điểm (nếu có stopline start)
        if len(positions) < 1:
            return 'unknown'
        
        current_time = time.time()
        end_pos = positions[-1]  # Vị trí hiện tại
        
        # ⚠️ CRITICAL: Ưu tiên dùng điểm bắt đầu từ stopline nếu có
        if track_id in self.stopline_start_positions:
            start_pos = self.stopline_start_positions[track_id]
            
            # Kiểm tra nếu đã quá 2s từ lúc qua stopline → bỏ qua
            time_diff = current_time - start_pos[2]
            if time_diff > self.time_window:
                # Quá 2s rồi, xóa stopline start và dùng logic cũ
                del self.stopline_start_positions[track_id]
                if len(positions) < 2:
                    return 'unknown'
                start_pos = positions[0]
            # else: Dùng stopline start position
        else:
            # Chưa qua stopline hoặc đã quá 2s, dùng điểm đầu trong window
            if len(positions) < 2:
                return 'unknown'
            start_pos = positions[0]
        
        # Tính vector di chuyển
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        
        # Tính khoảng cách di chuyển
        distance = math.sqrt(dx**2 + dy**2)
        
        # Nếu di chuyển quá ngắn, chưa đủ để xác định hướng
        if distance < self.min_distance:
            return 'unknown'
        
        # Tính góc (độ) -180 to 180
        angle = math.degrees(math.atan2(dy, dx))
        
        # Tính góc tương đối so với hướng tham chiếu
        relative_angle = angle - self.ref_angle
        
        # Chuẩn hóa về -180 to 180
        while relative_angle > 180:
            relative_angle -= 360
        while relative_angle < -180:
            relative_angle += 360
        
        # Phân loại hướng dựa trên relative_angle
        # relative_angle = 0° → đi thẳng
        # relative_angle < 0° → rẽ phải (clockwise)
        # relative_angle > 0° → rẽ trái (counter-clockwise)
        
        abs_rel = abs(relative_angle)
        
        # Đi thẳng: trong khoảng ±30°
        if abs_rel <= 30:
            return 'straight'
        
        # Rẽ phải: -90° to -30° (slight right to hard right)
        elif -90 <= relative_angle < -30:
            return 'right'
        
        # Rẽ trái: 30° to 90° (slight left to hard left)
        elif 30 < relative_angle <= 90:
            return 'left'
        
        # Góc quá lớn (> 90° hoặc < -90°) - có thể là U-turn hoặc noise
        else:
            return 'unknown'
    
    def get_direction(self, track_id: int) -> str:
        """Lấy hướng hiện tại của vehicle"""
        return self.directions.get(track_id, 'unknown')
    
    def set_ref_angle(self, ref_angle: float):
        """Cập nhật góc tham chiếu cho hướng đi thẳng"""
        self.ref_angle = ref_angle
        print(f"🧭 VehicleTracker: Updated ref_angle = {ref_angle:.1f}°")
    
    def clear(self):
        """Xóa toàn bộ tracking data"""
        self.positions.clear()
        self.directions.clear()

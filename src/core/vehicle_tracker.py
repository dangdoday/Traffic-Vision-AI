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
        self.vehicle_angles: Dict[int, float] = {}  # Store actual movement angle for each vehicle
        self.stopline_start_positions: Dict[int, Tuple[int, int, float]] = {}  # Điểm bắt đầu khi qua stopline
        self.locked_directions: Dict[int, str] = {}  # Directions locked when vehicle stopped
        self.last_significant_move_time: Dict[int, float] = {}  # Track when vehicle last moved significantly
        self.time_window = time_window  # 2 giây
        self.min_distance = min_distance  # 20 pixels
        self.ref_angle = ref_angle if ref_angle is not None else 90.0  # Default: 90° = xuống dưới
        self.stop_detection_window = 0.5  # 0.5s để detect xe dừng
    
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
            self.last_significant_move_time[track_id] = current_time
        
        # Thêm vị trí mới
        self.positions[track_id].append((x, y, current_time))
        
        # Xóa các vị trí cũ hơn time_window
        cutoff_time = current_time - self.time_window
        self.positions[track_id] = [
            pos for pos in self.positions[track_id] 
            if pos[2] >= cutoff_time
        ]
        
        # ⚠️ LOCK DIRECTION LOGIC: Detect when vehicle stopped
        # If direction is locked (xe dừng), return locked direction
        if track_id in self.locked_directions:
            # Check if vehicle is still stopped (movement < min_distance in stop_detection_window)
            stopped_time = current_time - self.last_significant_move_time.get(track_id, current_time)
            
            # If vehicle moved significantly again, unlock
            if self._check_significant_movement(track_id):
                # Vehicle started moving again - unlock direction
                del self.locked_directions[track_id]
                self.last_significant_move_time[track_id] = current_time
                # Recalculate direction
                direction = self._calculate_direction(track_id)
                self.directions[track_id] = direction
                return direction
            else:
                # Vehicle still stopped - return locked direction
                return self.locked_directions[track_id]
        
        # Tính direction (bình thường khi xe đang di chuyển)
        direction = self._calculate_direction(track_id)
        self.directions[track_id] = direction
        
        # ⚠️ Lock direction if vehicle is NOT moving significantly
        if direction != 'unknown' and not self._check_significant_movement(track_id):
            # Vehicle has stopped - lock current direction
            time_since_move = current_time - self.last_significant_move_time.get(track_id, current_time)
            if time_since_move > self.stop_detection_window:
                self.locked_directions[track_id] = direction
        elif direction != 'unknown':
            # Vehicle is moving - update last significant move time
            self.last_significant_move_time[track_id] = current_time
        
        return direction
    
    def _check_significant_movement(self, track_id: int) -> bool:
        """Check if vehicle moved significantly in recent frames"""
        if track_id not in self.positions or len(self.positions[track_id]) < 2:
            return False
        
        positions = self.positions[track_id]
        current_pos = positions[-1]
        
        # Check distance from all positions in stop_detection_window
        check_time = time.time() - self.stop_detection_window
        for pos in positions:
            if pos[2] < check_time:
                continue
            dx = current_pos[0] - pos[0]
            dy = current_pos[1] - pos[1]
            distance = math.sqrt(dx**2 + dy**2)
            if distance >= self.min_distance:
                return True
        
        return False
    
    def _calculate_direction(self, track_id: int) -> str:
        """Tính toán hướng di chuyển dựa trên time window"""
        if track_id not in self.positions:
            return 'unknown'
        
        positions = self.positions[track_id]
        
        # Cần ít nhất 1 điểm (nếu có stopline start)
        if len(positions) < 1:
            self.vehicle_angles[track_id] = None
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
                    self.vehicle_angles[track_id] = None
                    return 'unknown'
                start_pos = positions[0]
            # else: Dùng stopline start position
        else:
            # Chưa qua stopline hoặc đã quá 2s, dùng điểm đầu trong window
            if len(positions) < 2:
                self.vehicle_angles[track_id] = None
                return 'unknown'
            start_pos = positions[0]
        
        # Tính vector di chuyển
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        
        # Tính khoảng cách di chuyển
        distance = math.sqrt(dx**2 + dy**2)
        
        # Nếu di chuyển quá ngắn, chưa đủ để xác định hướng
        if distance < self.min_distance:
            self.vehicle_angles[track_id] = None
            return 'unknown'
        
        # Tính góc tuyệt đối (độ) -180 to 180
        absolute_angle = math.degrees(math.atan2(dy, dx))
        self.vehicle_angles[track_id] = absolute_angle  # ← Lưu góc tuyệt đối
        
        # Tính góc tương đối so với hướng tham chiếu
        relative_angle = absolute_angle - self.ref_angle
        
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
    
    def get_vehicle_angle(self, track_id: int) -> Optional[float]:
        """Lấy góc di chuyển tuyệt đối của vehicle (độ)"""
        return self.vehicle_angles.get(track_id)
    
    def get_angle_difference(self, track_id: int) -> Optional[float]:
        """Lấy độ lệch góc so với reference vector (độ, 0-180)
        
        Returns:
            Độ lệch trong khoảng [0, 180], None nếu không có data
        """
        vehicle_angle = self.vehicle_angles.get(track_id)
        if vehicle_angle is None:
            return None
        
        # Tính hiệu
        diff = vehicle_angle - self.ref_angle
        
        # Chuẩn hóa về -180 to 180
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        
        # Lấy giá trị tuyệt đối (0 to 180)
        return abs(diff)
    
    def set_ref_angle(self, ref_angle: float):
        """Cập nhật góc tham chiếu cho hướng đi thẳng"""
        self.ref_angle = ref_angle
        print(f"🧭 VehicleTracker: Updated ref_angle = {ref_angle:.1f}°")
    
    def clear(self):
        """Xóa toàn bộ tracking data"""
        self.positions.clear()
        self.directions.clear()
        self.vehicle_angles.clear()
        self.locked_directions.clear()
        self.last_significant_move_time.clear()
        self.stopline_start_positions.clear()

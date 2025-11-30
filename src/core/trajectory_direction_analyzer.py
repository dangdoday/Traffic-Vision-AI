"""
Trajectory Direction Analyzer - Phân tích hướng di chuyển từ trajectory
Sử dụng motion vector và góc chuyển động
"""
import numpy as np
import math
from typing import List, Tuple, Optional
from collections import deque


class TrajectoryDirectionAnalyzer:
    """
    Phân tích hướng di chuyển từ trajectory của vehicle
    
    Phương pháp:
    - Lưu lịch sử N vị trí gần nhất
    - Tính motion vector từ vị trí cũ → mới
    - Tính góc TƯƠNG ĐỐI so với reference vector (hướng đường thẳng)
    - Phân loại: left, right, straight
    
    HỖ TRỢ CAMERA NGHIÊNG: Sử dụng reference_vector để chuẩn hóa góc
    """
    
    def __init__(self, 
                 history_size: int = 15,
                 min_points: int = 5,
                 angle_threshold: float = 25.0,
                 reference_vector: Tuple[float, float] = None):
        """
        Args:
            history_size: Số lượng vị trí lưu trong lịch sử
            min_points: Số điểm tối thiểu để tính hướng
            angle_threshold: Ngưỡng góc để phân loại (độ)
                            > threshold: right
                            < -threshold: left
                            trong khoảng: straight
            reference_vector: Vector tham chiếu (dx, dy) cho hướng đi thẳng của đường
                             Nếu None, mặc định là (0, 1) - đi xuống theo trục Y
                             VD: Camera nghiêng 30°, reference = (sin(30°), cos(30°))
        """
        self.history_size = history_size
        self.min_points = min_points
        self.angle_threshold = angle_threshold
        
        # Reference vector: Hướng "đi thẳng" chuẩn của đường
        if reference_vector is None:
            self.reference_vector = np.array([0.0, 1.0])  # Mặc định: đi xuống
        else:
            self.reference_vector = np.array(reference_vector, dtype=float)
            # Normalize
            norm = np.linalg.norm(self.reference_vector)
            if norm > 0:
                self.reference_vector = self.reference_vector / norm
        
        # Lưu lịch sử vị trí: {track_id: deque([(x, y), ...])}
        self.trajectories = {}
        
        # Cache hướng đã tính: {track_id: direction}
        self.cached_directions = {}
    
    def set_reference_vector_from_points(self, p1: Tuple[int, int], p2: Tuple[int, int]):
        """
        Thiết lập reference vector từ 2 điểm trên đường thẳng
        
        Args:
            p1, p2: 2 điểm (x, y) xác định hướng đi thẳng của đường
                   VD: Điểm đầu và cuối của làn đường
        
        Example:
            analyzer.set_reference_vector_from_points((100, 200), (150, 600))
            # Đường nghiêng từ trên-trái xuống dưới-phải
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        self.reference_vector = np.array([dx, dy], dtype=float)
        
        # Normalize
        norm = np.linalg.norm(self.reference_vector)
        if norm > 0:
            self.reference_vector = self.reference_vector / norm
        
        angle_deg = math.degrees(math.atan2(dy, dx))
        print(f"🧭 Reference vector set: ({dx:.1f}, {dy:.1f}) → angle: {angle_deg:.1f}°")
    
    def set_reference_vector_from_angle(self, angle_degrees: float):
        """
        Thiết lập reference vector từ góc
        
        Args:
            angle_degrees: Góc của hướng đường (độ)
                          0° = East (→)
                          90° = South (↓)
                          -90° = North (↑)
                          
        Example:
            analyzer.set_reference_vector_from_angle(45)  # Đường nghiêng 45° xuống-phải
        """
        angle_rad = math.radians(angle_degrees)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        self.reference_vector = np.array([dx, dy], dtype=float)
        print(f"🧭 Reference vector set from angle: {angle_degrees}° → ({dx:.2f}, {dy:.2f})")
    
    def update_position(self, track_id: int, cx: int, cy: int):
        """
        Cập nhật vị trí mới cho vehicle
        
        Args:
            track_id: ID tracking
            cx, cy: Tọa độ tâm bbox
        """
        if track_id not in self.trajectories:
            self.trajectories[track_id] = deque(maxlen=self.history_size)
        
        self.trajectories[track_id].append((cx, cy))
    
    def get_trajectory_direction(self, track_id: int) -> str:
        """
        Tính hướng di chuyển dựa trên trajectory
        
        Returns:
            'left', 'right', 'straight', hoặc 'unknown'
        """
        if track_id not in self.trajectories:
            return 'unknown'
        
        trajectory = list(self.trajectories[track_id])
        
        if len(trajectory) < self.min_points:
            return 'unknown'
        
        # Tính góc chuyển hướng trung bình
        avg_angle = self._calculate_turning_angle(trajectory)
        
        # Phân loại dựa trên góc
        direction = self._classify_direction(avg_angle)
        
        # Cache kết quả
        self.cached_directions[track_id] = direction
        
        return direction
    
    def _calculate_turning_angle(self, trajectory: List[Tuple[int, int]]) -> float:
        """
        Tính góc rẽ TƯƠNG ĐỐI so với reference vector (hướng đường)
        
        Method:
        1. Tính vehicle motion vector từ điểm đầu → cuối
        2. So sánh với reference vector (hướng đi thẳng của đường)
        3. Tính góc lệch: dương = rẽ phải, âm = rẽ trái
        
        Returns:
            Góc lệch (độ), dương = rẽ phải, âm = rẽ trái, 0 = đi thẳng
        """
        if len(trajectory) < 2:
            return 0.0
        
        # Vehicle motion vector: từ điểm đầu → cuối
        start_point = np.array(trajectory[0], dtype=float)
        end_point = np.array(trajectory[-1], dtype=float)
        vehicle_vector = end_point - start_point
        
        # Normalize vehicle vector
        vehicle_norm = np.linalg.norm(vehicle_vector)
        if vehicle_norm < 1.0:  # Xe di chuyển quá ít
            return 0.0
        vehicle_vector = vehicle_vector / vehicle_norm
        
        # Tính góc giữa vehicle vector và reference vector
        # Sử dụng cross product để xác định chiều (trái/phải)
        cross = vehicle_vector[0] * self.reference_vector[1] - vehicle_vector[1] * self.reference_vector[0]
        dot = np.dot(vehicle_vector, self.reference_vector)
        
        # Góc tương đối (radian → degrees)
        angle_rad = math.atan2(cross, dot)
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
    
    def _classify_direction(self, angle: float) -> str:
        """
        Phân loại hướng dựa trên góc
        
        Args:
            angle: Góc chuyển hướng (độ)
                  Dương = rẽ phải
                  Âm = rẽ trái
        
        Returns:
            'left', 'right', 'straight'
        """
        if angle > self.angle_threshold:
            return 'right'
        elif angle < -self.angle_threshold:
            return 'left'
        else:
            return 'straight'
    
    def get_trajectory_info(self, track_id: int) -> dict:
        """
        Lấy thông tin chi tiết về trajectory
        
        Returns:
            Dict với keys: points_count, direction, angle, confidence
        """
        if track_id not in self.trajectories:
            return {'points_count': 0, 'direction': 'unknown', 'angle': 0.0, 'confidence': 0.0}
        
        trajectory = list(self.trajectories[track_id])
        points_count = len(trajectory)
        
        if points_count < self.min_points:
            return {
                'points_count': points_count,
                'direction': 'unknown',
                'angle': 0.0,
                'confidence': 0.0
            }
        
        angle = self._calculate_turning_angle(trajectory)
        direction = self._classify_direction(angle)
        
        # Tính confidence dựa trên số điểm và độ lớn góc
        confidence = min(1.0, points_count / self.history_size)
        if abs(angle) < self.angle_threshold / 2:
            confidence *= 0.8  # Giảm confidence nếu góc gần 0
        
        return {
            'points_count': points_count,
            'direction': direction,
            'angle': angle,
            'confidence': confidence
        }
    
    def draw_trajectory(self, frame, track_id: int, color=(255, 0, 255), thickness=2):
        """
        Vẽ trajectory lên frame
        
        Args:
            frame: Frame để vẽ
            track_id: ID của vehicle
            color: Màu đường trajectory
            thickness: Độ dày đường vẽ
        """
        if track_id not in self.trajectories:
            return frame
        
        trajectory = list(self.trajectories[track_id])
        
        if len(trajectory) < 2:
            return frame
        
        # Vẽ đường trajectory
        points = np.array(trajectory, dtype=np.int32)
        for i in range(len(points) - 1):
            cv2.line(frame, tuple(points[i]), tuple(points[i + 1]), color, thickness)
        
        # Vẽ điểm cuối (vị trí hiện tại)
        if len(trajectory) > 0:
            cv2.circle(frame, tuple(trajectory[-1]), 5, color, -1)
        
        return frame
    
    def clear_trajectory(self, track_id: int):
        """Xóa trajectory của một vehicle"""
        if track_id in self.trajectories:
            del self.trajectories[track_id]
        if track_id in self.cached_directions:
            del self.cached_directions[track_id]
    
    def clear_old_trajectories(self, active_track_ids: set):
        """
        Xóa trajectories của các vehicles không còn active
        
        Args:
            active_track_ids: Set các track_id đang active
        """
        # Tìm các track_id cần xóa
        to_remove = [tid for tid in self.trajectories.keys() 
                     if tid not in active_track_ids]
        
        for tid in to_remove:
            self.clear_trajectory(tid)

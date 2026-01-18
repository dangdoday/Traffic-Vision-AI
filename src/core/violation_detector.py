"""
Violation Detector - Phát hiện các loại vi phạm giao thông
"""
from typing import Set, Dict, Tuple, List, Optional


class ViolationDetector:
    """Quản lý phát hiện và theo dõi vi phạm"""
    
    def __init__(self):
        self.passed_vehicles: Set[int] = set()
        self.red_light_violators: Set[int] = set()
        self.lane_violators: Set[int] = set()
        self.direction_violators: Set[int] = set()  # Vehicles going wrong direction
        self.violator_track_ids: Set[int] = set()
        
        # Đếm phương tiện
        self.motorbike_count: Set[int] = set()
        self.car_count: Set[int] = set()
    
    def check_traffic_light_violation(
        self, 
        track_id: int, 
        vehicle_direction: str,
        traffic_lights: List[Tuple]
    ) -> Tuple[bool, str]:
        """
        Kiểm tra vi phạm đèn giao thông
        
        Args:
            track_id: ID của phương tiện
            vehicle_direction: Hướng di chuyển ('straight', 'left', 'right', 'unknown')
            traffic_lights: List các TL ROIs [(x1, y1, x2, y2, tl_type, color), ...]
        
        Returns:
            (is_violation, reason)
        """
        if not traffic_lights:
            return (False, "No traffic lights configured")
        
        # Thu thập trạng thái đèn
        has_any_green = False
        has_any_red = False
        has_circular_green = False
        has_matching_green_arrow = False
        
        green_lights = []
        red_lights = []
        
        for tl_data in traffic_lights:
            _, _, _, _, tl_type, color = tl_data
            
            if color == 'xanh' or color == 'den_xanh':
                has_any_green = True
                green_lights.append(tl_type)
                
                if tl_type == 'tròn':
                    has_circular_green = True
                elif tl_type == 'đi thẳng' and vehicle_direction == 'straight':
                    has_matching_green_arrow = True
                elif tl_type == 'rẽ trái' and vehicle_direction == 'left':
                    has_matching_green_arrow = True
                elif tl_type == 'rẽ phải' and vehicle_direction == 'right':
                    has_matching_green_arrow = True
            
            elif color == 'do' or color == 'den_do':
                has_any_red = True
                red_lights.append(tl_type)
        
        # Logic phát hiện vi phạm
        # 1. Đèn tròn xanh = ALLOWED (mọi hướng)
        if has_circular_green:
            return (False, f"✅ Circular GREEN light - ALLOWED")
        
        # 2. Có đèn xanh khớp với hướng = ALLOWED
        if has_matching_green_arrow:
            return (False, f"✅ Matching GREEN arrow ({vehicle_direction}) - ALLOWED")
        
        # 3. Có đèn đỏ và không có đèn xanh khớp = VIOLATION
        if has_any_red:
            if vehicle_direction == 'unknown':
                return (True, f"🚨 RED LIGHT VIOLATION - direction unknown ({', '.join(red_lights)})")
            else:
                return (True, f"🚨 RED LIGHT VIOLATION - {vehicle_direction} ({', '.join(red_lights)})")
        
        # 4. Chỉ có đèn xanh (không đỏ) = ALLOWED
        if has_any_green:
            return (False, f"✅ GREEN lights - ALLOWED ({', '.join(green_lights)})")
        
        # 5. Không rõ trạng thái đèn
        return (False, f"⚠️ No clear violation - dir={vehicle_direction}")
    
    def add_violation(self, track_id: int, violation_type: str):
        """Thêm vi phạm"""
        self.violator_track_ids.add(track_id)
        
        if violation_type == 'red_light':
            self.red_light_violators.add(track_id)
        elif violation_type == 'lane':
            self.lane_violators.add(track_id)
        elif violation_type == 'direction':
            self.direction_violators.add(track_id)
    
    def mark_vehicle_passed(self, track_id: int, vehicle_class: int):
        """Đánh dấu xe đã qua stopline và đếm theo loại"""
        self.passed_vehicles.add(track_id)
        
        # Đếm theo loại xe
        # 0: ô tô, 1: xe bus, 2: xe đạp, 3: xe máy, 4: xe tải
        if vehicle_class in [2, 3]:  # xe đạp, xe máy
            self.motorbike_count.add(track_id)
        elif vehicle_class in [0, 1, 4]:  # ô tô, xe bus, xe tải
            self.car_count.add(track_id)
    
    def is_violator(self, track_id: int) -> bool:
        """Kiểm tra xe có vi phạm không"""
        return track_id in self.violator_track_ids
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê vi phạm"""
        return {
            'total_vehicles': len(self.passed_vehicles),
            'motorbikes': len(self.motorbike_count),
            'cars': len(self.car_count),
            'red_light_violations': len(self.red_light_violators),
            'lane_violations': len(self.lane_violators),
            'direction_violations': len(self.direction_violators),
            'total_violations': len(self.violator_track_ids)
        }
    
    def clear(self):
        """Xóa toàn bộ dữ liệu vi phạm"""
        self.passed_vehicles.clear()
        self.red_light_violators.clear()
        self.lane_violators.clear()
        self.direction_violators.clear()
        self.violator_track_ids.clear()
        self.motorbike_count.clear()
        self.car_count.clear()

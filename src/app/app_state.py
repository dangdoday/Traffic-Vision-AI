"""
AppState giữ toàn bộ trạng thái chung cho ứng dụng
thay cho việc rải rác nhiều biến global.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

Point = Tuple[int, int]


@dataclass
class AppState:
    """
    - Video/model: đường dẫn video, model đang dùng, thông số model
    - ROI: lane, stopline, traffic light, direction ROI
    - Drawing: trạng thái đang vẽ + điểm tạm
    - Detection: cờ chạy, tập vi phạm, lịch sử tracking để tính hướng/tốc độ
    """

    # ===== Video / Model =====
    video_path: str = ""
    current_model: object = None
    current_model_type: Optional[str] = None
    model_config: Optional[Dict] = None
    available_models: Dict = field(default_factory=dict)

    # ===== ROI / Geometry =====
    lanes: List[Dict] = field(default_factory=list)  # [{"poly": [...], "allowed_labels": [...]}]
    stop_line: Optional[Tuple[Point, Point]] = None
    direction_rois: List[Dict] = field(default_factory=list)
    tl_rois: List[Tuple[int, int, int, int, str, str]] = field(default_factory=list)  # (x1,y1,x2,y2,tl_type,color)

    # ===== Drawing (temporary) =====
    drawing_mode: Optional[str] = None  # 'lane', 'stopline', 'direction_roi', 'tl_manual', 'ref_vector', ...
    tmp_lane_pts: List[Point] = field(default_factory=list)
    tmp_stop_point: Optional[Point] = None
    tmp_tl_point: Optional[Point] = None
    tmp_direction_pts: List[Point] = field(default_factory=list)
    selected_direction: str = "straight"

    # ===== Reference vector =====
    reference_vector_p1: Optional[Point] = None
    reference_vector_p2: Optional[Point] = None
    reference_vector_angle: Optional[float] = None

    # ===== Detection state =====
    detection_running: bool = False
    show_all_boxes: bool = True  # True = show all bbox, False = only violators

    violator_track_ids: Set[int] = field(default_factory=set)
    red_light_violators: Set[int] = field(default_factory=set)
    lane_violators: Set[int] = field(default_factory=set)
    passed_vehicles: Set[int] = field(default_factory=set)
    motorbike_ids: Set[int] = field(default_factory=set)
    car_ids: Set[int] = field(default_factory=set)

    # ===== Direction/speed history =====
    vehicle_positions: Dict[int, List[Tuple[int, int, float]]] = field(default_factory=dict)
    vehicle_directions: Dict[int, str] = field(default_factory=dict)

    # ===== Flags =====
    tl_tracking_active: bool = False

    # Helpers
    def reset_detection_state(self):
        self.detection_running = False
        self.violator_track_ids.clear()
        self.red_light_violators.clear()
        self.lane_violators.clear()
        self.passed_vehicles.clear()
        self.motorbike_ids.clear()
        self.car_ids.clear()
        self.vehicle_positions.clear()
        self.vehicle_directions.clear()

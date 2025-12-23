"""
Detection package
"""
from .traffic_light_detector import tl_pixel_state, classify_tl_color
from .direction_detector import calculate_vehicle_direction, estimate_vehicle_speed, set_vehicle_positions_ref
from .violation_checker import check_tl_violation, check_speed_violation, check_lane_direction_match, set_violation_checker_globals

__all__ = [
    'tl_pixel_state',
    'classify_tl_color',
    'calculate_vehicle_direction',
    'estimate_vehicle_speed',
    'set_vehicle_positions_ref',
    'check_tl_violation',
    'check_speed_violation',
    'check_lane_direction_match',
    'set_violation_checker_globals',
]



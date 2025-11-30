"""
Core Module - Traffic Violation Detection Logic
"""

from .violation_checker import (
    calculate_vehicle_direction,
    estimate_vehicle_speed,
    check_speed_violation,
    check_lane_direction_match,
    check_tl_violation
)

from .traffic_light_classifier import (
    tl_pixel_state,
    classify_tl_color,
    map_color_to_vietnamese
)

__all__ = [
    'calculate_vehicle_direction',
    'estimate_vehicle_speed',
    'check_speed_violation',
    'check_lane_direction_match',
    'check_tl_violation',
    'tl_pixel_state',
    'classify_tl_color',
    'map_color_to_vietnamese'
]

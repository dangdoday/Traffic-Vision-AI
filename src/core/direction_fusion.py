"""
Direction Fusion - Kết hợp ROI-based và Trajectory-based direction
"""
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DirectionFusion:
    """
    Kết hợp 2 nguồn thông tin để quyết định hướng cuối cùng:
    1. ROI-based direction (dựa vào vùng xe đang đi vào)
    2. Trajectory-based direction (dựa vào vector chuyển động)
    
    Nguyên lý:
    - Ưu tiên trajectory nếu rõ ràng (confidence cao)
    - Dùng ROI làm fallback khi trajectory chưa đủ dữ liệu
    - Phát hiện conflict (xe đi sai hướng so với ROI)
    """
    
    def __init__(self, 
                 trajectory_weight: float = 0.7,
                 min_trajectory_confidence: float = 0.5):
        """
        Args:
            trajectory_weight: Trọng số của trajectory (0.0 - 1.0)
            min_trajectory_confidence: Ngưỡng confidence tối thiểu để tin trajectory
        """
        self.trajectory_weight = trajectory_weight
        self.min_trajectory_confidence = min_trajectory_confidence
    
    def fuse_directions(self, 
                       roi_direction: Optional[str],
                       trajectory_direction: str,
                       trajectory_confidence: float = 0.0) -> Tuple[str, str, bool]:
        """
        Kết hợp ROI và Trajectory để ra quyết định cuối cùng
        
        Args:
            roi_direction: Hướng từ ROI ('left', 'right', 'straight', None)
            trajectory_direction: Hướng từ trajectory ('left', 'right', 'straight', 'unknown')
            trajectory_confidence: Độ tin cậy của trajectory (0.0 - 1.0)
        
        Returns:
            Tuple (final_direction, source, is_conflict)
            - final_direction: Hướng cuối cùng
            - source: Nguồn quyết định ('roi', 'trajectory', 'both', 'unknown')
            - is_conflict: True nếu ROI và trajectory khác nhau
        """
        # Case 1: Không có thông tin gì
        if roi_direction is None and trajectory_direction == 'unknown':
            return ('unknown', 'none', False)
        
        # Case 2: Chỉ có ROI, không có trajectory
        if roi_direction and trajectory_direction == 'unknown':
            logger.debug(f"Using ROI only: {roi_direction}")
            return (roi_direction, 'roi', False)
        
        # Case 3: Chỉ có trajectory, không có ROI
        if roi_direction is None and trajectory_direction != 'unknown':
            logger.debug(f"Using trajectory only: {trajectory_direction}")
            return (trajectory_direction, 'trajectory', False)
        
        # Case 4: Có cả ROI và trajectory
        # Kiểm tra conflict
        is_conflict = (roi_direction != trajectory_direction)
        
        # Sub-case 4.1: Trajectory confidence thấp → tin ROI
        if trajectory_confidence < self.min_trajectory_confidence:
            logger.debug(f"Low trajectory confidence ({trajectory_confidence:.2f}), using ROI: {roi_direction}")
            return (roi_direction, 'roi', is_conflict)
        
        # Sub-case 4.2: Cả hai giống nhau → perfect match
        if not is_conflict:
            logger.debug(f"ROI and trajectory agree: {roi_direction}")
            return (roi_direction, 'both', False)
        
        # Sub-case 4.3: Conflict → ưu tiên trajectory (xe có thể đi lệch ROI)
        logger.warning(f"⚠️  Direction conflict: ROI={roi_direction}, Trajectory={trajectory_direction} (conf={trajectory_confidence:.2f})")
        logger.warning(f"    → Using trajectory (vehicle may deviate from ROI)")
        return (trajectory_direction, 'trajectory', True)
    
    def get_confidence_explanation(self, 
                                   final_direction: str,
                                   source: str,
                                   is_conflict: bool,
                                   trajectory_confidence: float) -> str:
        """
        Tạo text giải thích cho quyết định
        
        Returns:
            String giải thích ngắn gọn
        """
        if source == 'none':
            return "❓ No data"
        
        elif source == 'roi':
            if is_conflict:
                return f"📍 ROI only (trajectory unclear)"
            return f"📍 ROI: {final_direction}"
        
        elif source == 'trajectory':
            if is_conflict:
                return f"🔄 Trajectory ({trajectory_confidence:.1%}) overrides ROI"
            return f"🔄 Trajectory: {final_direction} ({trajectory_confidence:.1%})"
        
        elif source == 'both':
            return f"✅ Both agree: {final_direction} ({trajectory_confidence:.1%})"
        
        return f"{final_direction}"
    
    def detect_violation(self, 
                        final_direction: str,
                        allowed_directions: list) -> Tuple[bool, str]:
        """
        Kiểm tra vi phạm hướng đi (nếu có quy định)
        
        Args:
            final_direction: Hướng đã xác định
            allowed_directions: List các hướng được phép ['left', 'straight', 'right']
        
        Returns:
            Tuple (is_violation, reason)
        """
        if not allowed_directions or 'all' in allowed_directions:
            return (False, "All directions allowed")
        
        if final_direction == 'unknown':
            return (False, "Direction unknown")
        
        if final_direction not in allowed_directions:
            return (True, f"Wrong direction: {final_direction} (allowed: {', '.join(allowed_directions)})")
        
        return (False, f"Correct direction: {final_direction}")


# Convenience function
def final_direction(roi_direction: Optional[str],
                   trajectory_direction: str,
                   trajectory_confidence: float = 0.0) -> str:
    """
    Hàm tiện ích để lấy hướng cuối cùng một cách đơn giản
    
    Returns:
        String: 'left', 'right', 'straight', 'unknown'
    """
    fusion = DirectionFusion()
    direction, _, _ = fusion.fuse_directions(
        roi_direction, 
        trajectory_direction, 
        trajectory_confidence
    )
    return direction

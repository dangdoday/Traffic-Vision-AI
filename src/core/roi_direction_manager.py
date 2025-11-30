"""
ROI Direction Manager - Quản lý ROIs và xác định hướng dựa trên vị trí
"""
import json
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class ROIDirectionManager:
    """Quản lý ROIs cho nhận diện hướng di chuyển"""
    
    def __init__(self, rois_json_path: str = None):
        self.rois: List[Dict] = []
        self.roi_polygons: List[np.ndarray] = []
        
        if rois_json_path and Path(rois_json_path).exists():
            self.load_rois(rois_json_path)
    
    def load_rois(self, json_path: str) -> bool:
        """Load ROIs từ file JSON"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.rois = data.get('rois', [])
            
            # Convert points sang numpy arrays
            self.roi_polygons = []
            for roi in self.rois:
                pts = np.array(roi['points'], dtype=np.int32)
                self.roi_polygons.append(pts)
            
            print(f"✅ Đã load {len(self.rois)} ROIs từ {json_path}")
            print(f"   - LEFT: {sum(1 for r in self.rois if r['direction'] == 'left')}")
            print(f"   - STRAIGHT: {sum(1 for r in self.rois if r['direction'] == 'straight')}")
            print(f"   - RIGHT: {sum(1 for r in self.rois if r['direction'] == 'right')}")
            return True
            
        except Exception as e:
            print(f"❌ Lỗi load ROIs: {e}")
            return False
    
    def get_roi_direction(self, cx: int, cy: int) -> Optional[str]:
        """
        Xác định hướng dựa trên vị trí centroid trong ROI
        
        Args:
            cx, cy: Tọa độ tâm bounding box
            
        Returns:
            'left', 'right', 'straight', hoặc None nếu không nằm trong ROI nào
        """
        if not self.rois:
            return None
        
        point = (cx, cy)
        
        # Kiểm tra từng ROI
        for i, polygon in enumerate(self.roi_polygons):
            # Sử dụng cv2.pointPolygonTest
            # Trả về: > 0 nếu inside, = 0 nếu on edge, < 0 nếu outside
            result = cv2.pointPolygonTest(polygon, point, False)
            
            if result >= 0:  # Inside hoặc on edge
                return self.rois[i]['direction']
        
        return None
    
    def get_roi_info(self, cx: int, cy: int) -> Optional[Dict]:
        """
        Lấy thông tin chi tiết của ROI chứa điểm
        
        Returns:
            Dict với keys: name, direction, points hoặc None
        """
        if not self.rois:
            return None
        
        point = (cx, cy)
        
        for i, polygon in enumerate(self.roi_polygons):
            if cv2.pointPolygonTest(polygon, point, False) >= 0:
                return self.rois[i].copy()
        
        return None
    
    def draw_rois(self, frame: np.ndarray, alpha: float = 0.3) -> np.ndarray:
        """
        Vẽ các ROIs lên frame với độ trong suốt
        
        Args:
            frame: Frame gốc
            alpha: Độ trong suốt (0.0 - 1.0)
            
        Returns:
            Frame đã vẽ ROIs
        """
        if not self.rois:
            return frame
        
        overlay = frame.copy()
        
        COLORS = {
            'left': (0, 0, 255),      # Đỏ
            'right': (0, 165, 255),   # Vàng
            'straight': (0, 255, 0),  # Xanh
            'unknown': (128, 128, 128)
        }
        
        for i, roi in enumerate(self.rois):
            pts = self.roi_polygons[i]
            color = COLORS.get(roi['direction'], COLORS['unknown'])
            
            # Fill polygon với độ trong suốt
            cv2.fillPoly(overlay, [pts], color)
            
            # Vẽ viền
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Vẽ label
            center = np.mean(pts, axis=0).astype(int)
            label = f"{roi['direction'].upper()}"
            cv2.putText(frame, label, tuple(center),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Blend overlay với frame gốc
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        return frame
    
    def draw_vehicle_roi(self, frame: np.ndarray, cx: int, cy: int, 
                        roi_direction: str) -> np.ndarray:
        """
        Vẽ dấu hiệu ROI direction cho vehicle
        
        Args:
            frame: Frame
            cx, cy: Tọa độ tâm vehicle
            roi_direction: Hướng từ ROI ('left', 'right', 'straight')
        """
        COLORS = {
            'left': (0, 0, 255),
            'right': (0, 165, 255),
            'straight': (0, 255, 0)
        }
        
        color = COLORS.get(roi_direction, (128, 128, 128))
        
        # Vẽ vòng tròn tại centroid
        cv2.circle(frame, (cx, cy), 8, color, -1)
        cv2.circle(frame, (cx, cy), 10, (255, 255, 255), 2)
        
        # Vẽ text ROI direction
        cv2.putText(frame, f"ROI:{roi_direction}", (cx + 15, cy),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê về ROIs"""
        if not self.rois:
            return {'total': 0, 'left': 0, 'straight': 0, 'right': 0}
        
        stats = {
            'total': len(self.rois),
            'left': sum(1 for r in self.rois if r['direction'] == 'left'),
            'straight': sum(1 for r in self.rois if r['direction'] == 'straight'),
            'right': sum(1 for r in self.rois if r['direction'] == 'right')
        }
        
        return stats

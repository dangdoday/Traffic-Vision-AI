"""
Configuration Manager for Traffic Violation Detection System
Saves and loads ROI configurations (lanes, stoplines, traffic lights, direction zones)
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def _safe_print(msg: str):
    """
    Print helper that avoids UnicodeEncodeError on Windows terminals that
    do not support UTF-8. Falls back to ASCII with replacement.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:
            # Last resort: drop the message
            pass


class ConfigManager:
    """Manages saving and loading of ROI configurations"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize ConfigManager
        
        Args:
            config_dir: Directory to store config files. If None, uses '../configs' relative to this file
        """
        if config_dir is None:
            # Default to configs folder in project root
            current_dir = Path(__file__).parent.parent.parent
            config_dir = current_dir / "configs"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        _safe_print(f"[Config] Directory: {self.config_dir}")
    
    def get_config_path(self, video_path: str) -> Path:
        """
        Get config file path for a video
        
        Args:
            video_path: Full path to video file
            
        Returns:
            Path to config file
        """
        # Extract video filename without extension
        video_name = Path(video_path).stem
        config_filename = f"{video_name}_config.json"
        return self.config_dir / config_filename
    
    def save_config(self, video_path: str, lane_configs: List[Dict], 
                   stop_line: Optional[Tuple], tl_rois: List[Tuple], 
                   direction_rois: List[Dict], 
                   reference_vector: Optional[Tuple] = None,
                   model_type: Optional[str] = None,
                   weight_name: Optional[str] = None,
                   imgsz: Optional[int] = None,
                   conf_threshold: Optional[float] = None) -> bool:
        """
        Save all ROI configurations to JSON file
        
        Args:
            video_path: Path to video file
            lane_configs: List of lane configurations
            stop_line: Stopline tuple ((x1,y1), (x2,y2)) or None
            tl_rois: List of traffic light ROIs
            direction_rois: List of direction zone ROIs
            reference_vector: Optional reference vector for tilted camera
            model_type: Optional model type (e.g., 'yolov8n', 'yolov8s')
            weight_name: Optional weight filename
            imgsz: Optional image size for detection
            conf_threshold: Optional confidence threshold
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            config_path = self.get_config_path(video_path)
            
            # Debug: Log what we're serializing
            _safe_print(f"[Config] Saving to: {config_path}")
            _safe_print(f"[Config] Lanes: {len(lane_configs)}, Stopline: {stop_line is not None}, TLs: {len(tl_rois)}, DirROIs: {len(direction_rois)}")
            
            # Prepare data structure with error handling for each part
            try:
                lanes_serialized = self._serialize_lanes(lane_configs)
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing lanes: {e}")
                lanes_serialized = []
            
            try:
                stopline_serialized = self._serialize_stopline(stop_line)
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing stopline: {e}")
                stopline_serialized = None
            
            try:
                tl_serialized = self._serialize_traffic_lights(tl_rois)
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing traffic lights: {e}")
                import traceback
                traceback.print_exc()
                tl_serialized = []
            
            try:
                dir_serialized = self._serialize_direction_zones(direction_rois)
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing direction zones: {e}")
                dir_serialized = []
            
            try:
                ref_serialized = self._serialize_reference_vector(reference_vector)
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing reference vector: {e}")
                ref_serialized = None
            
            config_data = {
                'video_name': Path(video_path).name,
                'video_path': str(video_path),
                'lanes': lanes_serialized,
                'stopline': stopline_serialized,
                'traffic_lights': tl_serialized,
                'direction_zones': dir_serialized,
                'reference_vector': ref_serialized,
                'model': {
                    'type': model_type,
                    'weight': weight_name,
                    'imgsz': imgsz,
                    'conf_threshold': conf_threshold
                }
            }
            
            # Write to file with pretty formatting
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            _safe_print(f"[Config] Saved: {config_path}")
            return True
            
        except Exception as e:
            _safe_print(f"[Config] Failed to save: {e}")
            return False
    
    def load_config(self, video_path: str) -> Optional[Dict]:
        """
        Load ROI configuration from JSON file
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with all ROI data, or None if config doesn't exist
        """
        try:
            config_path = self.get_config_path(video_path)
            
            if not config_path.exists():
                _safe_print(f"[Config] No saved config for this video: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Deserialize all components
            result = {
                'lanes': self._deserialize_lanes(config_data.get('lanes', [])),
                'stopline': self._deserialize_stopline(config_data.get('stopline')),
                'traffic_lights': self._deserialize_traffic_lights(config_data.get('traffic_lights', [])),
                'direction_zones': self._deserialize_direction_zones(config_data.get('direction_zones', [])),
                'reference_vector': self._deserialize_reference_vector(config_data.get('reference_vector')),
                'model': config_data.get('model', {})
            }
            
            _safe_print(f"[Config] Loaded: {config_path}")
            _safe_print(f"   - Lanes: {len(result['lanes'])}")
            _safe_print(f"   - Stopline: {'Yes' if result['stopline'] else 'No'}")
            _safe_print(f"   - Traffic Lights: {len(result['traffic_lights'])}")
            _safe_print(f"   - Direction Zones: {len(result['direction_zones'])}")
            if result['model']:
                _safe_print(f"   - Model: {result['model'].get('type', 'N/A')} ({result['model'].get('weight', 'N/A')})")
            
            return result
            
        except Exception as e:
            _safe_print(f"[Config] Failed to load: {e}")
            return None
    
    def config_exists(self, video_path: str) -> bool:
        """Check if config file exists for a video"""
        return self.get_config_path(video_path).exists()
    
    # Serialization methods
    def _serialize_lanes(self, lane_configs: List[Dict]) -> List[Dict]:
        """Convert lane configs to JSON-serializable format"""
        serialized = []
        for lane in lane_configs:
            # Support both 'points' and 'poly' keys
            points = lane.get('points', lane.get('poly', []))
            # Support both 'allowed_types' and 'allowed_labels' keys
            allowed = lane.get('allowed_types', lane.get('allowed_labels', []))
            serialized.append({
                'points': points,
                'label': lane.get('label', 'Unnamed Lane'),
                'allowed_types': allowed
            })
        return serialized
    
    def _serialize_stopline(self, stop_line: Optional[Tuple]) -> Optional[Dict]:
        """Convert stopline to JSON-serializable format"""
        if stop_line is None:
            return None
        p1, p2 = stop_line
        return {
            'p1': list(p1),
            'p2': list(p2)
        }
    
    def _serialize_traffic_lights(self, tl_rois: List[Tuple]) -> List[Dict]:
        """Convert traffic light ROIs to JSON-serializable format"""
        serialized = []
        for i, tl in enumerate(tl_rois):
            try:
                # Format: (x1, y1, x2, y2, tl_type, current_color)
                if len(tl) != 6:
                    _safe_print(f"[Config] WARNING: TL {i} has {len(tl)} elements, expected 6: {tl}")
                    continue
                x1, y1, x2, y2, tl_type, current_color = tl
                serialized.append({
                    'x1': int(x1),
                    'y1': int(y1),
                    'x2': int(x2),
                    'y2': int(y2),
                    'type': str(tl_type),
                    'color': str(current_color) if current_color else 'unknown'
                })
            except Exception as e:
                _safe_print(f"[Config] ERROR serializing TL {i}: {e}, data={tl}")
        return serialized
    
    def _serialize_direction_zones(self, direction_rois: List[Dict]) -> List[Dict]:
        """Convert direction ROIs to JSON-serializable format"""
        serialized = []
        for roi in direction_rois:
            serialized.append({
                'name': roi.get('name', 'Unnamed'),
                'points': roi['points'],
                'allowed_directions': roi.get('allowed_directions', ['straight']),
                'primary_direction': roi.get('primary_direction', 'straight'),
                'direction': roi.get('direction', 'straight')  # Backward compat
            })
        return serialized
    
    def _serialize_reference_vector(self, ref_vector: Optional[Tuple]) -> Optional[Dict]:
        """Convert reference vector to JSON-serializable format"""
        if ref_vector is None:
            return None
        # Format: ((x1, y1), (x2, y2))
        p1, p2 = ref_vector
        return {
            'p1': list(p1),
            'p2': list(p2)
        }
    
    # Deserialization methods
    def _deserialize_lanes(self, lanes_data: List[Dict]) -> List[Dict]:
        """Convert JSON data back to lane configs"""
        lanes = []
        for lane in lanes_data:
            lanes.append({
                'points': lane['points'],
                'label': lane.get('label', 'Unnamed Lane'),
                'allowed_types': lane.get('allowed_types', [])
            })
        return lanes
    
    def _deserialize_stopline(self, stopline_data: Optional[Dict]) -> Optional[Tuple]:
        """Convert JSON data back to stopline tuple"""
        if stopline_data is None:
            return None
        p1 = tuple(stopline_data['p1'])
        p2 = tuple(stopline_data['p2'])
        return (p1, p2)
    
    def _deserialize_traffic_lights(self, tl_data: List[Dict]) -> List[Tuple]:
        """Convert JSON data back to traffic light ROIs"""
        tl_rois = []
        for tl in tl_data:
            # Reconstruct tuple format: (x1, y1, x2, y2, tl_type, current_color)
            tl_tuple = (
                tl['x1'],
                tl['y1'],
                tl['x2'],
                tl['y2'],
                tl['type'],
                tl.get('color', 'unknown')  # Default to unknown if not saved
            )
            tl_rois.append(tl_tuple)
        return tl_rois
    
    def _deserialize_direction_zones(self, direction_data: List[Dict]) -> List[Dict]:
        """Convert JSON data back to direction ROIs"""
        direction_rois = []
        for roi in direction_data:
            direction_rois.append({
                'name': roi.get('name', 'Unnamed'),
                'points': roi['points'],
                'allowed_directions': roi.get('allowed_directions', ['straight']),
                'primary_direction': roi.get('primary_direction', 'straight'),
                'direction': roi.get('direction', 'straight')
            })
        return direction_rois
    
    def _deserialize_reference_vector(self, ref_data: Optional[Dict]) -> Optional[Tuple]:
        """Convert JSON data back to reference vector"""
        if ref_data is None:
            return None
        p1 = tuple(ref_data['p1'])
        p2 = tuple(ref_data['p2'])
        return (p1, p2)

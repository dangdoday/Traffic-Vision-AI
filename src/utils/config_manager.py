"""
Configuration Manager for Traffic Violation Detection System
Saves and loads ROI configurations (lanes, stoplines, traffic lights, direction zones)
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional


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
        print(f"[Config] Config directory: {self.config_dir}")
    
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
                   reference_vector: Optional[Tuple] = None) -> bool:
        """
        Save all ROI configurations to JSON file
        
        Args:
            video_path: Path to video file
            lane_configs: List of lane configurations
            stop_line: Stopline tuple ((x1,y1), (x2,y2)) or None
            tl_rois: List of traffic light ROIs
            direction_rois: List of direction zone ROIs
            reference_vector: Optional reference vector for tilted camera
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            config_path = self.get_config_path(video_path)
            
            # Prepare data structure
            config_data = {
                'video_name': Path(video_path).name,
                'video_path': str(video_path),
                'lanes': self._serialize_lanes(lane_configs),
                'stopline': self._serialize_stopline(stop_line),
                'traffic_lights': self._serialize_traffic_lights(tl_rois),
                'direction_zones': self._serialize_direction_zones(direction_rois),
                'reference_vector': self._serialize_reference_vector(reference_vector)
            }
            
            # Write to file with pretty formatting
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] Configuration saved: {config_path}")
            return True
            
        except Exception as e:
            print(f"[X] Failed to save config: {e}")
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
                print(f"ℹ️ No config found for this video: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Deserialize all components
            result = {
                'lanes': self._deserialize_lanes(config_data.get('lanes', [])),
                'stopline': self._deserialize_stopline(config_data.get('stopline')),
                'traffic_lights': self._deserialize_traffic_lights(config_data.get('traffic_lights', [])),
                'direction_zones': self._deserialize_direction_zones(config_data.get('direction_zones', [])),
                'reference_vector': self._deserialize_reference_vector(config_data.get('reference_vector'))
            }
            
            print(f"[OK] Configuration loaded: {config_path}")
            print(f"   - Lanes: {len(result['lanes'])}")
            print(f"   - Stopline: {'Yes' if result['stopline'] else 'No'}")
            print(f"   - Traffic Lights: {len(result['traffic_lights'])}")
            print(f"   - Direction Zones: {len(result['direction_zones'])}")
            
            return result
            
        except Exception as e:
            print(f"[X] Failed to load config: {e}")
            return None
    
    def config_exists(self, video_path: str) -> bool:
        """Check if config file exists for a video"""
        return self.get_config_path(video_path).exists()
    
    # Serialization methods
    def _serialize_lanes(self, lane_configs: List[Dict]) -> List[Dict]:
        """Convert lane configs to JSON-serializable format"""
        serialized = []
        for lane in lane_configs:
            # Support both 'poly' and 'points' keys for backward compatibility
            points = lane.get('poly', lane.get('points', []))
            serialized.append({
                'points': points,
                'label': lane.get('label', 'Unnamed Lane'),
                'allowed_types': lane.get('allowed_types', []),
                'allowed_labels': lane.get('allowed_labels', ['all'])
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
        for tl in tl_rois:
            # Format: (x1, y1, x2, y2, tl_type, current_color)
            x1, y1, x2, y2, tl_type, current_color = tl
            serialized.append({
                'x1': int(x1),
                'y1': int(y1),
                'x2': int(x2),
                'y2': int(y2),
                'type': tl_type,
                'color': current_color  # Save last known color (optional)
            })
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
                'poly': lane['points'],  # Use 'poly' key for integrated_main.py compatibility
                'label': lane.get('label', 'Unnamed Lane'),
                'allowed_types': lane.get('allowed_types', []),
                'allowed_labels': lane.get('allowed_labels', ['all'])
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

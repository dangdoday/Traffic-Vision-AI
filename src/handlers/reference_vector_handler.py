"""
Reference Vector Handler Mixin
Contains methods for setting reference vector for camera angle calibration
"""
import sys
import math
from PyQt5.QtWidgets import QMessageBox


class ReferenceVectorHandlerMixin:
    """Mixin class for reference vector handling in MainWindow"""
    
    def _get_globals(self):
        """Get globals from the main module - handles both __main__ and integrated_main cases"""
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'TL_ROIS') and hasattr(main_module, 'LANE_CONFIGS'):
                return main_module
        import integrated_main
        return integrated_main
    
    def start_set_reference_vector(self):
        """Bắt đầu vẽ reference vector"""
        main = self._get_globals()
        
        if self.current_frame is None:
            QMessageBox.warning(self, "No Frame", "No video frame available.")
            return
        
        main._drawing_mode = 'ref_vector'
        self.ref_vector_p1 = None
        self.ref_vector_p2 = None
        self.btn_finish_ref_vector.setEnabled(True)
        self.status_label.setText("Status: Click 2 points on STRAIGHT lane (start → end)")
        print("🧭 Setting Reference Vector: Click 2 points on straight lane")
    
    def finish_reference_vector(self):
        """Hoàn thành reference vector"""
        main = self._get_globals()
        
        if self.ref_vector_p1 is None or self.ref_vector_p2 is None:
            QMessageBox.warning(self, "Incomplete", "Need 2 points for reference vector!")
            return
        
        # Tính vector và góc
        dx = self.ref_vector_p2[0] - self.ref_vector_p1[0]
        dy = self.ref_vector_p2[1] - self.ref_vector_p1[1]
        length = math.sqrt(dx**2 + dy**2)
        
        if length < 10:
            QMessageBox.warning(self, "Too Short", "Reference vector too short! Choose points farther apart.")
            return
        
        angle = math.degrees(math.atan2(dy, dx))
        
        # Cập nhật label
        self.ref_vector_label.setText(f"Ref Vector: {angle:.1f}° ({dx:.0f}, {dy:.0f})")
        
        print(f"✅ Reference Vector Set:")
        print(f"   Point 1: {self.ref_vector_p1}")
        print(f"   Point 2: {self.ref_vector_p2}")
        print(f"   Vector: ({dx:.1f}, {dy:.1f})")
        print(f"   Angle: {angle:.2f}°")
        
        # ⚠️ CRITICAL: Update VehicleTracker with reference angle
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.set_reference_angle(angle)
            print(f"🎯 Applied ref_angle={angle:.1f}° to VehicleTracker")
        else:
            print(f"⚠️ Warning: VideoThread not initialized yet, ref_angle will be applied when video loads")
        
        main._drawing_mode = None
        self.btn_finish_ref_vector.setEnabled(False)
        self.status_label.setText(f"Status: Reference vector set ({angle:.1f}°)")
        
        QMessageBox.information(self, "Reference Vector Set", 
                               f"Reference vector set successfully!\n\n"
                               f"Angle: {angle:.1f}°\n"
                               f"This will be used to calculate vehicle turning directions\n"
                               f"relative to the straight road direction.")

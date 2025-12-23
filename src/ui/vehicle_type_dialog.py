"""
Vehicle Type Selection Dialog
Allows user to select which vehicle types are allowed in a lane
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
    QPushButton, QLabel, QDialogButtonBox
)


class VehicleTypeDialog(QDialog):
    """Dialog for selecting allowed vehicle types in a lane"""
    
    # Vehicle types matching YOLO model classes
    VEHICLE_TYPES = {
        'ô tô': 'Ô tô (Car)',
        'xe bus': 'Xe bus (Bus)',
        'xe đạp': 'Xe đạp (Bicycle)',
        'xe máy': 'Xe máy (Motorbike)',
        'xe tải': 'Xe tải (Truck)'
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn loại phương tiện được phép")
        self.setMinimumWidth(300)
        
        self.selected_types = []
        self.checkboxes = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("<b>Chọn loại phương tiện được phép đi trong làn này:</b>")
        layout.addWidget(header)
        
        # Checkboxes for each vehicle type
        for key, label in self.VEHICLE_TYPES.items():
            cb = QCheckBox(label)
            cb.setChecked(True)  # Default: all types allowed
            self.checkboxes[key] = cb
            layout.addWidget(cb)
        
        # Select all / Deselect all buttons
        btn_layout = QHBoxLayout()
        
        btn_all = QPushButton("Chọn tất cả")
        btn_all.clicked.connect(self._select_all)
        btn_layout.addWidget(btn_all)
        
        btn_none = QPushButton("Bỏ chọn tất cả")
        btn_none.clicked.connect(self._deselect_all)
        btn_layout.addWidget(btn_none)
        
        layout.addLayout(btn_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def _select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)
    
    def _deselect_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)
    
    def get_selected(self):
        """Return list of selected vehicle type keys"""
        selected = []
        for key, cb in self.checkboxes.items():
            if cb.isChecked():
                selected.append(key)
        
        # If nothing selected, return 'all' as default
        if not selected:
            return ['all']
        
        return selected

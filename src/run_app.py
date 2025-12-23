#!/usr/bin/env python
"""
Traffic Violation Detector - Main Entry Point

This is the new modularized entry point that uses refactored modules.
The old integrated_main.py is kept for backward compatibility.

Directory Structure:
- app/detection/: Traffic light detection, direction detection, violation checking
- app/geometry/: Geometry utility functions
- app/state/: Application state management  
- core/: Vehicle tracking, violation detection (OOP modules)
- ui/: UI components
- utils/: Config manager and utilities
"""

if __name__ == '__main__':
    # Import and run from integrated_main.py
    # In future, this can be replaced with full modular implementation
    from integrated_main import main
    main()

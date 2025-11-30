# src/app/controllers/lane_controller.py
"""
LaneController: quản lý vẽ/xóa lane và đồng bộ danh sách UI.
"""

from app.app_state import AppState
from ui.lane_selector import VehicleTypeDialog


class LaneController:
    def __init__(self, state: AppState, window):
        self.state = state
        self.window = window

    # =========================================================
    # 1. Bắt đầu vẽ lane
    # =========================================================
    def start_add_lane(self):
        self.state.drawing_mode = "lane"
        self.state.tmp_lane_pts.clear()

        self.window.status_label.setText(
            "Status: Click on video to draw lane. Press 'Finish Lane' when done."
        )

        if hasattr(self.window, "btn_add_lane"):
            try:
                self.window.btn_add_lane.setText("Finish Lane")
                self.window.btn_add_lane.clicked.disconnect()
            except Exception:
                pass
            self.window.btn_add_lane.clicked.connect(self.finish_lane)

        print("Lane drawing mode ON")

    def handle_lane_click(self, x: int, y: int):
        if self.state.drawing_mode != "lane":
            return

        self.state.tmp_lane_pts.append((x, y))
        self.window.status_label.setText(
            f"Status: Lane points = {len(self.state.tmp_lane_pts)}"
        )

    # =========================================================
    # 2. Hoàn thành lane
    # =========================================================
    def finish_lane(self):
        if len(self.state.tmp_lane_pts) < 3:
            self.window.status_label.setText("Status: Need at least 3 points for a lane")
            print("Lane needs >= 3 points")
            return

        poly = list(self.state.tmp_lane_pts)
        dialog = VehicleTypeDialog(self.window)

        if dialog.exec_() == dialog.Accepted:
            allowed = dialog.get_selected()
            lane_cfg = {"poly": poly, "allowed_labels": allowed}
            self.state.lanes.append(lane_cfg)

            self.window.status_label.setText(
                "Status: Lane added with vehicles: " + ", ".join(allowed)
            )
            print(f"Lane added - allowed vehicles: {allowed}")
        else:
            print("Lane creation cancelled by user")

        self.state.tmp_lane_pts.clear()
        self.state.drawing_mode = None

        if hasattr(self.window, "btn_add_lane"):
            try:
                self.window.btn_add_lane.setText("Add Lane (Click on video)")
                self.window.btn_add_lane.clicked.disconnect()
            except Exception:
                pass
            self.window.btn_add_lane.clicked.connect(self.start_add_lane)

        self.update_lane_list_widget()
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    # =========================================================
    # 3. Xóa lane
    # =========================================================
    def delete_selected_lane(self):
        if not hasattr(self.window, "lane_list"):
            return

        selected = self.window.lane_list.currentRow()
        if selected < 0 or selected >= len(self.state.lanes):
            print("No lane selected to delete")
            return

        del self.state.lanes[selected]
        print(f"Lane {selected + 1} deleted")

        self.update_lane_list_widget()
        self.window.status_label.setText(f"Status: Deleted lane {selected + 1}")
        if hasattr(self.window, "_apply_thread_globals"):
            self.window._apply_thread_globals()

    # =========================================================
    # 4. Cập nhật danh sách UI
    # =========================================================
    def update_lane_list_widget(self):
        if not hasattr(self.window, "lane_list"):
            return

        self.window.lane_list.clear()
        for idx, lane in enumerate(self.state.lanes, start=1):
            allowed = lane.get("allowed_labels", ["all"]) or ["all"]
            poly = lane.get("poly", [])
            self.window.lane_list.addItem(
                f"Lane {idx}: {len(poly)} points - {', '.join(allowed)}"
            )

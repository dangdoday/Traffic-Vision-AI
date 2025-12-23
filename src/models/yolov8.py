class YOLOv8:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = self.load_model()

    def load_model(self):
        from ultralytics import YOLO
        return YOLO(self.model_path)

    def predict(self, frame):
        results = self.model(frame)
        return results

    def track(self, frame, imgsz=640, conf=0.25, classes=None, tracker="bytetrack.yaml", persist=True):
        results = self.model.track(
            frame,
            imgsz=imgsz,
            conf=conf,
            classes=classes,
            tracker=tracker,
            persist=persist
        )
        return results

    def switch_model(self, new_model_path):
        self.model_path = new_model_path
        self.model = self.load_model()
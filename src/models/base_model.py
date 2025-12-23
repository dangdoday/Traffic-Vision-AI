class BaseModel:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None

    def load_model(self):
        """Load the model from the specified path."""
        raise NotImplementedError("Subclasses should implement this method.")

    def predict(self, input_data):
        """Make a prediction using the loaded model."""
        raise NotImplementedError("Subclasses should implement this method.")
def read_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")
    return cap

def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return None
    return frame

def display_frame(frame, window_name="Video"):
    cv2.imshow(window_name, frame)

def release_video(cap):
    cap.release()
    cv2.destroyAllWindows()

def save_frame(frame, output_path):
    cv2.imwrite(output_path, frame)
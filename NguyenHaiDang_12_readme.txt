Traffic-Vision-AI - Group 12

1) Thong tin thanh vien va phan viec
- Nguyen Hai Dang (22001560):
  + Thu thap, gan nhan data
  + Xay dung UI, README huong dan su dung
  + Thuat toan ByteTrack, logic xac dinh huong xe di chuyen
- Nguyen Mau Duc (22001568):
  + Thu thap, gan nhan data
  + Xay dung logic phat hien vi pham, logic phat hien mau den giao thong HSV
  + Viet bao cao
- Chu Van Hiep (22001576):
  + Huan luyen mo hinh YOLOv8
  + Viet bao cao
  + Hoan thien slide

2) Huong dan tai du lieu va link tuong ung
- Dataset chinh (phuong tien + bien so): TODO_LINK_1
- Dataset bo sung/kiem thu: TODO_LINK_2
- Huong dan tai:
  a) Tai file tu link tren.
  b) Giai nen vao thu muc data/ (xem muc 3).
  c) Dam bao cau truc images/ va labels/ dung chuan YOLO.

3) Cach to chuc thu muc / kich ban thuc nghiem (theo repo hien tai)
- Cau truc thu muc:
  Traffic-Vision-AI/
    src/
      integrated_main.py
      model_config.py
      app/
        detection/
        geometry/
        state/
      core/
      handlers/
      managers/
      models/
      tools/
      ui/
      utils/
    models/
      README.md
      yolov8/
        *.pt
    configs/
      *_config.json
    docs/
      COMPLETE_LOGIC_ANALYSIS.md
      COMPLETE_VIOLATION_CASES.md
      DIRECTION_DETECTION.md
      DIRECTION_INTEGRATION_GUIDE.md
      TRAFFIC_LIGHT_RULES_VN.md
    Figures/
    requirements.txt
    SYSTEM_PIPELINE.md
    LATEX_SETUP_GUIDE.md
    test_ocr.py
    README.md
    .gitignore
    .vscode/

- Kich ban thuc nghiem (theo code):
  a) Chay GUI kiem thu:
     python src/integrated_main.py
  b) Test OCR:
     python test_ocr.py
  c) Ve ROI bang tools (neu can):
     python src/tools/roi_direction_editor.py --video path/to/video.mp4
     python src/tools/reference_vector_calibrator.py --video path/to/video.mp4
  d) Luu/tai cau hinh ROI:
     - Luu: Ctrl+S (file luu vao configs/<video>_config.json)
     - Tai: Ctrl+L
  e) Train YOLOv8:
     - Repo khong co script train. Dung Ultralytics CLI va bo sung dataset.yaml ben ngoai.

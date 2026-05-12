import cv2
import numpy as np
from paddleocr import PaddleOCR
import warnings
warnings.filterwarnings('ignore')

plate_img = np.ones((100, 300, 3), dtype=np.uint8) * 255
cv2.putText(plate_img, '29B12345', (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)

ocr = PaddleOCR(lang='en', use_textline_orientation=True)
print('Testing PaddleOCR with new API:')
result = ocr.ocr(plate_img)
print(f'Result type: {type(result)}')
print(f'Result: {result}')
if result and len(result) > 0:
    print(f'First item: {result[0]}')
    if isinstance(result[0], list) and len(result[0]) > 0:
        print(f'First detection: {result[0][0]}')

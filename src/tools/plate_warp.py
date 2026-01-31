import cv2
import numpy as np


def order_points(pts):
    """Order 4 points: tl, tr, br, bl"""
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype="float32")


def four_point_warp(img, quad):
    """Perspective warp using 4 corners"""
    quad = order_points(quad)
    (tl, tr, br, bl) = quad

    W = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    H = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))

    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, M, (W, H))


def warp_minarearect_from_black_regions(
    img_bgr,
    upscale=8,
    remove_blue_box=True,
):
    """Find dark regions in the plate crop, compute minAreaRect and warp.

    Returns (warped, up_clean, mask_used, box)
    - warped: the perspective-corrected image (frontal view)
    - up_clean: upscaled cleaned input used for visualization
    - mask_used: mask of dark regions used to find contours
    - box: 4-point float32 box used for warping
    """
    # 1) Upscale to make edges easier to detect
    up = cv2.resize(img_bgr, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)

    # 2) Optionally remove blue bbox overlay
    if remove_blue_box:
        hsv = cv2.cvtColor(up, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([90, 80, 80])
        upper_blue = np.array([140, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        up = cv2.inpaint(up, blue_mask, 3, cv2.INPAINT_TELEA)

    # 3) Mask dark regions (border + characters)
    hsv2 = cv2.cvtColor(up, cv2.COLOR_BGR2HSV)
    dark = cv2.inRange(hsv2, np.array([0, 0, 0]), np.array([180, 255, 110]))

    # 4) Morphology to join dark regions
    dark = cv2.morphologyEx(
        dark, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
        iterations=2
    )

    # 5) Get gradient/dilate to emphasize frame
    grad = cv2.morphologyEx(
        dark, cv2.MORPH_GRADIENT,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    )
    grad = cv2.dilate(
        grad, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
        iterations=1
    )
    grad = cv2.morphologyEx(
        grad, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (13, 13)),
        iterations=2
    )

    # 6) Find largest contour → minAreaRect
    cnts, _ = cv2.findContours(grad, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError("Không tìm thấy contour. Thử tăng V-threshold hoặc chỉnh kernel.")

    c = max(cnts, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)         # ((cx,cy),(w,h), angle)
    box = cv2.boxPoints(rect)         # 4 points
    box = box.astype(np.float32)

    # 7) Warp perspective
    warped = four_point_warp(up, box)

    return warped, up, grad, box


if __name__ == "__main__":
    print("Module plate_warp - helper for plate perspective correction")

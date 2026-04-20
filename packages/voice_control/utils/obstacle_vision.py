import cv2
import numpy as np

_ROI_Y_START = 0.55   # fraction of frame height
_ROI_X_MARGIN = 0.15  # fraction trimmed off each side

# Morphological kernel for cleaning up mask noise.
_MORPH_KERNEL = np.ones((5, 5), np.uint8)

# Coloured/dark blob must cover this fraction of the ROI to count as close.
_MIN_BLOB_FRACTION = 0.06

# White-wall detection. Walls are large white blobs; lane lines are also
_WHITE_LOW = np.array([0, 0, 180], dtype=np.uint8)
_WHITE_HIGH = np.array([180, 60, 255], dtype=np.uint8)
_WALL_MIN_AREA_FRACTION = 0.08
_WALL_MAX_ELONGATION = 4.0   


def _has_white_wall(hsv, roi_area) -> bool:
    """True if a blocky (non-elongated) white region fills enough of the ROI
    to be a wall. Lane lines get rejected here because their minAreaRect is
    very long relative to its short side."""
    white = cv2.inRange(hsv, _WHITE_LOW, _WHITE_HIGH)
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, _MORPH_KERNEL)

    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        if cv2.contourArea(c) < roi_area * _WALL_MIN_AREA_FRACTION:
            continue
        (_, _), (bw, bh), _ = cv2.minAreaRect(c)
        long_side = max(bw, bh)
        short_side = max(min(bw, bh), 1.0)
        if long_side / short_side > _WALL_MAX_ELONGATION:
            continue
        return True
    return False


def detect_close_obstacle(frame) -> bool:
    """True if a large non-road object sits in the near-field ROI."""
    h, w = frame.shape[:2]
    roi = frame[int(h * _ROI_Y_START):,
                int(w * _ROI_X_MARGIN):int(w * (1 - _ROI_X_MARGIN))]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_area = roi.shape[0] * roi.shape[1]

    if _has_white_wall(hsv, roi_area):
        return True

    coloured = cv2.inRange(hsv, (0, 80, 40), (180, 255, 255))
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 255, 40))
    mask = cv2.bitwise_or(coloured, dark)

    yellow_lane = cv2.inRange(hsv, (20, 80, 100), (35, 255, 255))
    mask = cv2.bitwise_and(mask, cv2.bitwise_not(yellow_lane))

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _MORPH_KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _MORPH_KERNEL)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False

    largest = max(cv2.contourArea(c) for c in contours)
    return largest > roi_area * _MIN_BLOB_FRACTION

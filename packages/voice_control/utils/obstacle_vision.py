import cv2
import numpy as np

_ROI_Y_START = 0.55   # fraction of frame height
_ROI_X_MARGIN = 0.15  # fraction trimmed off each side

# Morphological kernel for cleaning up mask noise.
_MORPH_KERNEL = np.ones((5, 5), np.uint8)

# Blob must cover this fraction of the ROI to count as a close obstacle.
_MIN_BLOB_FRACTION = 0.06


def detect_close_obstacle(frame) -> bool:
    """True if a large non-road object sits in the near-field ROI."""
    h, w = frame.shape[:2]
    roi = frame[int(h * _ROI_Y_START):,
                int(w * _ROI_X_MARGIN):int(w * (1 - _ROI_X_MARGIN))]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Candidate pixels: saturated colours OR near-black (road is neither).
    coloured = cv2.inRange(hsv, (0, 80, 40), (180, 255, 255))
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 255, 40))
    mask = cv2.bitwise_or(coloured, dark)

    # Yellow lane paint is saturated yellow on the ground — exclude it so we
    # don't flag the centre line as an obstacle.
    yellow_lane = cv2.inRange(hsv, (20, 80, 100), (35, 255, 255))
    mask = cv2.bitwise_and(mask, cv2.bitwise_not(yellow_lane))

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _MORPH_KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _MORPH_KERNEL)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False

    roi_area = mask.shape[0] * mask.shape[1]
    largest = max(cv2.contourArea(c) for c in contours)
    return largest > roi_area * _MIN_BLOB_FRACTION

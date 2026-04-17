import cv2
import numpy as np

# Minimum pixel area
MIN_AREA = 300

# HSV thresholds for traffic light colors
RED_LOW_1 = np.array([0, 120, 100], dtype=np.uint8)
RED_HIGH_1 = np.array([10, 255, 255], dtype=np.uint8)
RED_LOW_2 = np.array([160, 120, 100], dtype=np.uint8)
RED_HIGH_2 = np.array([180, 255, 255], dtype=np.uint8)

YELLOW_LOW = np.array([15, 120, 100], dtype=np.uint8)
YELLOW_HIGH = np.array([35, 255, 255], dtype=np.uint8)

GREEN_LOW = np.array([40, 80, 80], dtype=np.uint8)
GREEN_HIGH = np.array([85, 255, 255], dtype=np.uint8)


def detect_traffic_light(frame):
    """Detect the dominant traffic light color in the frame.

    Returns:
        "red", "yellow", "green", or None if no traffic light detected.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Only look at the upper portion of the frame where lights would be
    h = hsv.shape[0]
    roi = hsv[:int(h * 0.6), :]

    red_mask = cv2.inRange(roi, RED_LOW_1, RED_HIGH_1) | cv2.inRange(roi, RED_LOW_2, RED_HIGH_2)
    yellow_mask = cv2.inRange(roi, YELLOW_LOW, YELLOW_HIGH)
    green_mask = cv2.inRange(roi, GREEN_LOW, GREEN_HIGH)

    red_area = _circular_area(red_mask)
    yellow_area = _circular_area(yellow_mask)
    green_area = _circular_area(green_mask)

    best = max(red_area, yellow_area, green_area)
    if best < MIN_AREA:
        return None

    if best == red_area:
        return "red"
    elif best == yellow_area:
        return "yellow"
    else:
        return "green"


def _circular_area(mask):
    """Find the largest roughly circular contour area in the mask."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0

    max_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity > 0.4:
            max_area = max(max_area, area)
    return max_area

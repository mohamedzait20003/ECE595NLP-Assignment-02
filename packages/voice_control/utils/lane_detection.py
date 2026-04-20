import cv2
import numpy as np

YELLOW_LOW = np.array([20, 80, 80], dtype=np.uint8)
YELLOW_HIGH = np.array([35, 255, 255], dtype=np.uint8)

WHITE_LOW = np.array([0, 0, 180], dtype=np.uint8)
WHITE_HIGH = np.array([180, 60, 255], dtype=np.uint8)

_MIN_CONTOUR_AREA = 200


def preprocess(frame):
    h = frame.shape[0]
    cropped = frame[int(h * 0.4):, :]
    return cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)


def _centroid_x(mask):
    """Centroid x over the whole mask — used for the yellow centreline, whose
    dashed segments collectively describe a single line down the middle."""
    M = cv2.moments(mask)
    if M["m00"] < 500:
        return None
    return M["m10"] / M["m00"]


def _extreme_contour_cx(mask, side):
    """Centroid x of the leftmost or rightmost valid contour. Used to pick a
    single side boundary when both white lines are visible at once."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        if cv2.contourArea(c) < _MIN_CONTOUR_AREA:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = M["m10"] / M["m00"]
        if best is None:
            best = cx
        elif side == "right" and cx > best:
            best = cx
        elif side == "left" and cx < best:
            best = cx
    return best


def _line_slope(mask):
    """Fit a line to ALL mask pixels — robust to dashed yellow where picking
    the single largest contour would snap to a random dash per frame."""
    ys, xs = np.where(mask > 0)
    if len(xs) < 20:
        return 0.0
    pts = np.column_stack((xs, ys)).astype(np.float32)
    vx, vy, *_ = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    return float(vx / (vy + 1e-6))


def detect_lane(frame):
    hsv = preprocess(frame)
    h, w = hsv.shape[:2]
    image_center = w / 2.0

    yellow_mask = cv2.inRange(hsv, YELLOW_LOW, YELLOW_HIGH)
    white_mask = cv2.inRange(hsv, WHITE_LOW, WHITE_HIGH)

    yellow_cx = _centroid_x(yellow_mask)

    if yellow_cx is not None:
        if yellow_cx < image_center:
            white_side, lane_offset = "right", +w * 0.25
        else:
            white_side, lane_offset = "left", -w * 0.25
        white_cx = _extreme_contour_cx(white_mask, white_side)
        # Sanity: the chosen white must be on the far side of yellow.
        if white_cx is not None:
            if white_side == "right" and white_cx < yellow_cx:
                white_cx = None
            elif white_side == "left" and white_cx > yellow_cx:
                white_cx = None
    else:
        white_cx = _centroid_x(white_mask)
        lane_offset = -w * 0.25 if (white_cx or 0) > image_center else w * 0.25

    if yellow_cx is None and white_cx is None:
        return None, None

    if yellow_cx is not None and white_cx is not None:
        lane_center = (yellow_cx + white_cx) / 2.0
    elif yellow_cx is not None:
        lane_center = yellow_cx + lane_offset
    else:
        lane_center = white_cx + lane_offset

    lateral_error = (lane_center - image_center) / image_center
    heading_error = _line_slope(yellow_mask) if yellow_cx is not None else 0.0
    return lateral_error, heading_error

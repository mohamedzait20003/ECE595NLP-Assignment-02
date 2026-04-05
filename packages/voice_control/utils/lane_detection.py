import cv2
import numpy as np

# Define color thresholds for lane detection
YELLOW_LOW = np.array([20, 80, 80], dtype=np.uint8)
YELLOW_HIGH = np.array([35, 255, 255], dtype=np.uint8)

WHITE_LOW = np.array([0, 0, 180], dtype=np.uint8)
WHITE_HIGH = np.array([180, 60, 255], dtype=np.uint8)


def preprocess(frame):
    h = frame.shape[0]
    cropped = frame[int(h*0.4):, :]
    return cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)

def _centroid_x(mask):
    M = cv2.moments(mask)
    if M["m00"] < 500:
        return None
    
    return M["m10"] / M["m00"]

def _line_slope(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return 0.0
    
    pts = np.vstack(max(contours, key=cv2.contourArea)).squeeze()
    if pts.ndim < 2 or len(pts) < 2:
        return 0.0
    
    vx, vy, *_ = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    return float(vx / (vy + 1e-6))

def detect_lane(frame):
    hsv = preprocess(frame)
    h, w = hsv.shape[:2]

    yellow_mask = cv2.inRange(hsv, YELLOW_LOW, YELLOW_HIGH)
    white_mask = cv2.inRange(hsv, WHITE_LOW, WHITE_HIGH)

    yellow_cx = _centroid_x(yellow_mask)
    white_cx = _centroid_x(white_mask)

    if yellow_cx is None and white_cx is None:
        return None, None

    if yellow_cx is not None and white_cx is not None:
        lane_center = (yellow_cx + white_cx) / 2.0
    elif yellow_cx is not None:
        lane_center = yellow_cx + w * 0.25
    else:
        lane_center = white_cx - w * 0.25

    image_center = w / 2.0
    lateral_error = (lane_center - image_center) / image_center
    
    heading_error = _line_slope(yellow_mask) if yellow_cx is not None else 0.0
    return lateral_error, heading_error

    

import os

# ── Driving ───────────────────────────────────────────────────────────────────
DEFAULT_SPEED      = float(os.getenv("DEFAULT_SPEED", "0.4"))   # m/s
MAX_SPEED          = float(os.getenv("MAX_SPEED",     "0.6"))
MIN_SPEED          = float(os.getenv("MIN_SPEED",     "0.1"))
SPEED_STEP         = float(os.getenv("SPEED_STEP",    "0.1"))

# ── Lane Following PD gains ───────────────────────────────────────────────────
KP = float(os.getenv("KP", "2.0"))
KD = float(os.getenv("KD", "0.5"))

# ── Safety ────────────────────────────────────────────────────────────────────
OBSTACLE_STOP_DIST = float(os.getenv("OBSTACLE_STOP_DIST", "0.30"))  # meters
HEARTBEAT_TIMEOUT  = float(os.getenv("HEARTBEAT_TIMEOUT",  "4.0"))   # seconds

# ── Calibration ───────────────────────────────────────────────────────────────
FORWARD_TRIM = float(os.getenv("FORWARD_TRIM", "0.0"))

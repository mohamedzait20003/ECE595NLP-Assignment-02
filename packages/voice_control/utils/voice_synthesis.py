import re
from .load_config import DEFAULT_SPEED

FAST_PATTERNS = {
    r'\bstop\b':           {"cmd": "stop",        "v": 0.0,           "omega":  0.0},
    r'\b(go|forward)\b':   {"cmd": "forward",     "v": DEFAULT_SPEED, "omega":  0.0},
    r'\bturn left\b':      {"cmd": "turn",         "v": 0.0,           "omega":  1.5},
    r'\bturn right\b':     {"cmd": "turn",         "v": 0.0,           "omega": -1.5},
    r'\bpass left\b':      {"cmd": "pass",         "side": "left"},
    r'\bpass right\b':     {"cmd": "pass",         "side": "right"},
    r'\b(follow|lane)\b':  {"cmd": "lane_follow",  "enable": True,    "v": DEFAULT_SPEED},
    r'\bmanual\b':         {"cmd": "lane_follow",  "enable": False,   "v": 0.0},
    r'\breverse\b':        {"cmd": "reverse",      "v": DEFAULT_SPEED},
}


class VoiceSynthesis:
    """Parses spoken text into a command dict using regex pattern matching."""

    def parse(self, text: str) -> dict | None:
        """Return a command dict, or None if no pattern matches."""
        lower = text.lower()
        for pattern, cmd in FAST_PATTERNS.items():
            if re.search(pattern, lower):
                return cmd
        return None

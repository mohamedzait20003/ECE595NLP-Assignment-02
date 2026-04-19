import re
from typing import Optional
from .load_config import DEFAULT_SPEED

FAST_PATTERNS = {
    r'\bstop\b':                                          {"cmd": "stop",        "v": 0.0,           "omega":  0.0},
    r'\b(turn around|u-?turn|youey|uey)\b':               {"cmd": "turn_around"},
    r'\bcross\b.*\bleft\b':                               {"cmd": "cross_lane",  "side": "left"},
    r'\bcross\b.*\bright\b':                              {"cmd": "cross_lane",  "side": "right"},
    r'\b(turn|go) left\b':                                {"cmd": "turn",        "v": 0.0,           "omega":  1.5},
    r'\b(turn|go) right\b':                               {"cmd": "turn",        "v": 0.0,           "omega": -1.5},
    r'\b(go|forward)\b':                                  {"cmd": "forward",     "v": DEFAULT_SPEED, "omega":  0.0},
    r'\bpass left\b':                                     {"cmd": "pass",        "side": "left"},
    r'\bpass right\b':                                    {"cmd": "pass",        "side": "right"},
    r'\b(follow|lane)\b':                                 {"cmd": "lane_follow", "enable": True,     "v": DEFAULT_SPEED},
    r'\bmanual\b':                                        {"cmd": "lane_follow", "enable": False,    "v": 0.0},
    r'\breverse\b':                                       {"cmd": "reverse",     "v": DEFAULT_SPEED},
    r'\b(increase speed|speed up|faster)\b':              {"cmd": "speed_up"},
    r'\b(decrease speed|slow down|slower)\b':             {"cmd": "speed_down"},
}


class VoiceSynthesis:
    """Parses spoken text into a command dict using regex pattern matching."""

    def parse(self, text: str) -> Optional[dict]:
        """Return a command dict, or None if no pattern matches."""
        lower = text.lower()
        for pattern, cmd in FAST_PATTERNS.items():
            if re.search(pattern, lower):
                return cmd
        return None

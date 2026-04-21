import re
from typing import Optional
from .load_config import DEFAULT_SPEED

# Order matters — more specific patterns must come before more general ones.
# e.g. "max speed" must be checked before the generic "increase speed" would
# otherwise also match, and "override" must come before any movement pattern.
FAST_PATTERNS = {
    r'\bstop\b':                                          {"cmd": "stop",        "v": 0.0,           "omega":  0.0},
    r'\b(override|ignore obstacles?|force (forward|move)|go anyway)\b': {"cmd": "override"},
    r'\b(max|maximum|full|top)(\s+\w+)?\s+speed\b':       {"cmd": "max_speed"},
    r'\b(turn around|u-?turn|youey|uey)\b':               {"cmd": "turn_around"},
    r'\bcross\b.*\bleft\b':                               {"cmd": "cross_lane",  "side": "left"},
    r'\bcross\b.*\bright\b':                              {"cmd": "cross_lane",  "side": "right"},
    r'\b(maneuver|manoeuvre|swerve|veer)\s+left\b':       {"cmd": "maneuver",    "v": DEFAULT_SPEED, "omega":  2.0},
    r'\b(maneuver|manoeuvre|swerve|veer)\s+right\b':      {"cmd": "maneuver",    "v": DEFAULT_SPEED, "omega": -2.0},
    r'\b(turn|go) left\b':                                {"cmd": "turn",        "v": 0.0,           "omega":  3.0},
    r'\b(turn|go) right\b':                               {"cmd": "turn",        "v": 0.0,           "omega": -3.0},
    r'\bpass left\b':                                     {"cmd": "pass",        "side": "left",     "v": DEFAULT_SPEED, "omega":  2.0},
    r'\bpass right\b':                                    {"cmd": "pass",        "side": "right",    "v": DEFAULT_SPEED, "omega": -2.0},
    r'\b(follow|lane)\b':                                 {"cmd": "lane_follow", "enable": True,     "v": DEFAULT_SPEED},
    r'\bmanual\b':  {"cmd": "lane_follow", "enable": False,    "v": 0.0},
    r'\breverse\b': {"cmd": "reverse",     "v": DEFAULT_SPEED},
    r'\b(increase(\s+\w+)?\s+speed|speed(\s+\w+)?\s+up|faster)\b': {"cmd": "speed_up"},
    r'\b(decrease(\s+\w+)?\s+speed|slow(\s+\w+)?\s+down|slower)\b': {"cmd": "speed_down"},
    r'\b(go|forward|move)\b': {"cmd": "forward",     "v": DEFAULT_SPEED, "omega":  0.0},
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

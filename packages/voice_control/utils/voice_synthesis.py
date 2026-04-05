import re
import json
from openai import AzureOpenAI
from .load_config import (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, DEFAULT_SPEED)

GPT_SYSTEM_PROMPT = """
You control a Duckiebot. Convert the spoken command to JSON only. No explanation.
Valid commands:
  {"cmd":"forward","v":<0.1-0.6>,"omega":0.0}
  {"cmd":"stop"}
  {"cmd":"turn","v":0.0,"omega":<+1.5 left | -1.5 right>}
  {"cmd":"speed_adjust","v":<speed>}
  {"cmd":"lane_follow","enable":<true|false>,"v":<speed>}
  {"cmd":"pass","side":"left"|"right"}
  {"cmd":"reverse","v":<speed>}
"""

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
    """Parses spoken text into a command dict.

    Strategy:
      1. _fast_path — regex match on critical keywords (<250 ms, no network)
      2. _gpt_path  — Azure OpenAI GPT-4o-mini for everything else (~500 ms)
    """

    def __init__(self):
        self._client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-02-01"
        )

    def parse(self, text: str) -> dict | None:
        """Return a command dict, or None if parsing fails."""
        cmd = self._fast_path(text)
        if cmd is not None:
            return cmd
        return self._gpt_path(text)

    # ── private ──────────────────────────────────────────────────────────────

    def _fast_path(self, text: str) -> dict | None:
        lower = text.lower()
        for pattern, cmd in FAST_PATTERNS.items():
            if re.search(pattern, lower):
                return cmd
        return None

    def _gpt_path(self, text: str) -> dict | None:
        try:
            resp = self._client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": GPT_SYSTEM_PROMPT},
                    {"role": "user",   "content": text}
                ],
                max_tokens=60,
                temperature=0
            )
            raw = resp.choices[0].message.content.strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

import os
from dotenv import load_dotenv

load_dotenv()  # loads from .env file at repo root (or CWD)

# ── Azure Speech ──────────────────────────────────────────────────────────────
AZURE_SPEECH_KEY    = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.environ["AZURE_SPEECH_REGION"]

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT   = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_KEY        = os.environ["AZURE_OPENAI_KEY"]
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

# ── Audio ─────────────────────────────────────────────────────────────────────
AUDIO_DEVICE_INDEX = int(os.getenv("AUDIO_DEVICE_INDEX", "0"))

# ── Driving ───────────────────────────────────────────────────────────────────
DEFAULT_SPEED      = float(os.getenv("DEFAULT_SPEED", "0.4"))   # m/s
MAX_SPEED          = float(os.getenv("MAX_SPEED",     "0.6"))

# ── Lane Following PD gains ───────────────────────────────────────────────────
KP = float(os.getenv("KP", "2.0"))
KD = float(os.getenv("KD", "0.5"))

# ── Safety ────────────────────────────────────────────────────────────────────
OBSTACLE_STOP_DIST = float(os.getenv("OBSTACLE_STOP_DIST", "0.15"))  # meters
HEARTBEAT_TIMEOUT  = float(os.getenv("HEARTBEAT_TIMEOUT",  "2.0"))   # seconds

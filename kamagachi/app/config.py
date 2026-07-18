"""Tunable constants + environment loading. Every gamification number lives here."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# ─── SECRETS / ENV ────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = _env("TELEGRAM_WEBHOOK_SECRET", "kamagachi-secret")
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", "http://localhost:8000")

STAY22_API_KEY = _env("STAY22_API_KEY")
STAY22_AFFILIATE_ID = _env("STAY22_AFFILIATE_ID", "kamagachi")

MONGODB_URI = _env("MONGODB_URI")
MONGODB_DB = _env("MONGODB_DB", "kamagachi")

GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.0-flash-exp")

ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_DYING = _env("ELEVENLABS_VOICE_DYING", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_VOICE_ALIVE = _env("ELEVENLABS_VOICE_ALIVE", "EXAVITQu4vr4xnSDxMaL")

# ─── GAMIFICATION CONSTANTS (tune LIVE during demo) ──────────────────────────
@dataclass(frozen=True)
class Gamification:
    START_HEALTH: int = 0
    MAX_HEALTH: int = 100

    # Phase 1 heals
    HEAL_CONSTRAINTS_LOCKED: int = 10  # budget + group_size
    HEAL_CITIES_RESOLVED: int = 20     # full city list
    HEAL_DATES_MAPPED: int = 20        # all date windows

    # Phase 2 milestones
    PHASE_STABLE_HEALTH: int = 50
    HEAL_PER_SWIPE: int = 1
    HEAL_UNANIMOUS_MATCH: int = 20
    HEAL_VERIFIED_BOOKING: int = 100   # jumps to full

    # Decay
    DECAY_INACTIVITY_24H: int = -15
    DECAY_AVAILABILITY_DROP: int = -25
    DECAY_PRICE_SPIKE: int = -25
    DECAY_MAX_PER_CYCLE: int = -30

    # Market thresholds (triggers)
    MARKET_AVAILABILITY_THRESHOLD_PCT: float = 5.0   # ≥5% drop
    MARKET_PRICE_THRESHOLD_USD: float = 15.0         # ≥$15 nightly spike

    # Voice escalation
    VOICE_THRESHOLD_HEALTH: int = 25   # below this and pet may call the group
    VOICE_ESCALATION_MIN_MINUTES: int = 10

    # Poller cadence
    MARKET_POLL_SECONDS: int = 60
    INACTIVITY_CHECK_SECONDS: int = 300


GAMIFY = Gamification()


# ─── PET STATE THRESHOLDS ─────────────────────────────────────────────────────
def pet_state(health: int) -> str:
    """Maps health → sprite/animation state."""
    if health >= 95:
        return "golden"
    if health >= 70:
        return "happy"
    if health >= 40:
        return "stable"
    if health >= 15:
        return "sick"
    return "dying"


# ─── DEMO / SEED ──────────────────────────────────────────────────────────────
DEMO_MODE = _env("DEMO_MODE", "1") == "1"  # allows the app to run without every key

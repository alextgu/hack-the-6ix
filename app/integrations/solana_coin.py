"""Solana "Japan Trip Coin" — a post-commit devnet souvenir. FULLY ISOLATED.

Called ONCE from bot.cmd_commit AFTER the booking/graduation has posted. The
caller wraps it fire-and-forget + try/except, so a mint failure is logged and
swallowed and the booking/graduation ALWAYS completes regardless.

Devnet only — never mainnet, never real funds. If SOLANA_TREASURY_SECRET is
unset the mint is skipped silently. The on-chain work lives in solana/mint.mjs
(@solana/web3.js + @solana/spl-token); this module shapes the metadata, runs
that script with a timeout, and parses its JSON. Never raises.

Config (env):
  SOLANA_TREASURY_SECRET  devnet keypair (JSON secret array or base58). Required.
  SOLANA_CLUSTER          default "devnet". "mainnet*" is refused as a safety.
  TRIP_COIN_IMAGE_URL     coin art URL (on-chain metadata ref + chat image).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger("trippet.solana")

_MINT_SCRIPT = Path(__file__).resolve().parents[2] / "solana" / "mint.mjs"
_TIMEOUT_S = 90


def _as_date(v) -> Optional[date]:
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def format_trip_name(city: Optional[str], start, end) -> str:
    """'Osaka · Apr 12–18' (or '· Apr 30 – May 3' across months)."""
    city = (city or "Japan").strip()
    s, e = _as_date(start), _as_date(end)
    if not s:
        return f"{city} Trip"
    if e and e.month == s.month:
        span = f"{s.strftime('%b')} {s.day}–{e.day}"
    elif e:
        span = f"{s.strftime('%b')} {s.day} – {e.strftime('%b')} {e.day}"
    else:
        span = s.strftime("%b %d")
    return f"{city} · {span}"


def _config_ready() -> bool:
    secret = os.environ.get("SOLANA_TREASURY_SECRET", "").strip()
    cluster = os.environ.get("SOLANA_CLUSTER", "devnet").strip().lower()
    if not secret:
        log.info("trip coin: SOLANA_TREASURY_SECRET unset — skipping mint (booking unaffected)")
        return False
    if cluster.startswith("mainnet"):
        log.warning("trip coin: cluster=%s refused — souvenir is devnet-only, skipping", cluster)
        return False
    return True


def mint_trip_coin(trip: dict, group_id: int) -> Optional[dict]:
    """Mint the souvenir coin on devnet. `trip` = {"name", "booking_url"}.
    Returns {mint, explorer_url, name, image_url, signature, booking_url} on
    success, or None if skipped/failed. NEVER raises — the caller's booking
    flow must never be affected by this."""
    if not _config_ready():
        return None
    name = str((trip or {}).get("name") or "Japan Trip")
    booking_url = str((trip or {}).get("booking_url") or "")
    # Souvenir metadata attributes — all optional, empty string = omitted.
    location = str((trip or {}).get("location") or "")
    time_spent = str((trip or {}).get("time_spent") or "")
    slacker = str((trip or {}).get("slacker") or "")
    co2e_saved = str((trip or {}).get("co2e_saved") or "")
    try:
        env = {
            **os.environ,
            "COIN_NAME": name,
            "COIN_BOOKING_URL": booking_url,
            "COIN_LOCATION": location,
            "COIN_TIME_SPENT": time_spent,
            "COIN_SLACKER": slacker,
            "COIN_CO2E": co2e_saved,
            "SOLANA_CLUSTER": os.environ.get("SOLANA_CLUSTER", "devnet"),
        }
        proc = subprocess.run(
            ["node", str(_MINT_SCRIPT)],
            env=env, capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
        res = json.loads((proc.stdout or "").strip() or "{}")
    except Exception as e:
        log.warning("trip coin mint failed (group=%s): %s: %s — booking unaffected",
                    group_id, type(e).__name__, e)
        return None

    if not res.get("ok"):
        log.warning("trip coin mint skipped (group=%s): %s — booking unaffected",
                    group_id, res.get("reason") or "unknown")
        return None

    log.info("trip coin minted (group=%s): %s → %s", group_id, res.get("mint"), res.get("explorer"))
    return {
        "mint": res.get("mint"),
        "explorer_url": res.get("explorer"),
        "signature": res.get("signature"),
        "name": name,
        "booking_url": booking_url,
        "location": location or None,
        "time_spent": time_spent or None,
        "slacker": slacker or None,
        "co2e_saved": co2e_saved or None,
        "image_url": os.environ.get("TRIP_COIN_IMAGE_URL", "").strip() or None,
    }


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    demo = {"name": format_trip_name("Osaka", "2027-04-12", "2027-04-18"),
            "booking_url": "https://allez.stay22.com/demo"}
    print("minting:", demo["name"])
    print(json.dumps(mint_trip_coin(demo, group_id=-1) or {"result": "skipped/failed (see log)"}, indent=2))

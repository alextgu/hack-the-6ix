"""Standalone probe for Stay22's Direct Travel API.

Not wired into anything. No imports from the app. Just: hit the accommodations
endpoint once, print the response, save a sample to disk, and surface where
price/availability live in the first few results.

Params verified against:
  - https://api.stay22.com/openapi.json  (GET /v2/accommodations)
  - https://dev.stay22.com/docs/api/accommodations/search

Usage:
  python stay22_probe.py
  STAY22_AID=your_partner_id python stay22_probe.py
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta
from pathlib import Path


ENDPOINT = "https://api.stay22.com/v2/accommodations"
OUT_FILE = Path(__file__).parent / "sample_response.json"


def build_request() -> tuple[str, dict[str, str]]:
    checkin = date.today() + timedelta(weeks=6)
    checkout = checkin + timedelta(days=2)
    params: dict[str, str | int | float] = {
        # location
        "address": "Tokyo, Japan",
        # dates (must be today-or-later; format YYYY-MM-DD)
        "checkin": checkin.isoformat(),
        "checkout": checkout.isoformat(),
        # occupancy
        "adults": 2,
        "rooms": 1,
        # currency
        "currency": "USD",
        # pagination — pull enough to see supplier variety
        "pageSize": 10,
        "page": 1,
    }
    aid = os.environ.get("STAY22_AID", "").strip()
    if aid:
        params["aid"] = aid
        params["campaign"] = "trippet_probe"

    qs = urllib.parse.urlencode(params)
    url = f"{ENDPOINT}?{qs}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "stay22-probe/1.0 (trippet hackathon)",
    }
    return url, headers


def call(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        print(f"NETWORK ERROR: {e}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    url, headers = build_request()
    print(f"→ GET {url}")
    print(f"  aid: {'set' if os.environ.get('STAY22_AID') else 'unset (keyless demo)'}")

    status, body = call(url, headers)
    print(f"← HTTP {status}\n")

    # Always attempt JSON parse; if it's not JSON, just dump raw.
    try:
        data = json.loads(body)
        pretty = json.dumps(data, indent=2, sort_keys=False)
    except json.JSONDecodeError:
        print("(response was not JSON)")
        print(body.decode("utf-8", errors="replace"))
        sys.exit(1)

    print("=== FULL RESPONSE ===")
    print(pretty)

    OUT_FILE.write_bytes(body)
    print(f"\n→ saved {len(body)} bytes to {OUT_FILE.name}")

    if status >= 400:
        print("(request failed — leaving the sample file in place for inspection)")
        sys.exit(1)

    results = data.get("results") or []
    if not results:
        print("(no `results` array in payload — check the shape above)")
        return

    print(f"\n=== FIRST {min(3, len(results))} PROPERTIES — name + suppliers ===")
    for r in results[:3]:
        name = r.get("name", "?")
        pid = r.get("id", "?")
        suppliers = r.get("suppliers") or r.get("supplier") or {}
        print(f"\n• {name}  (id={pid})")
        print(json.dumps(suppliers, indent=2))


if __name__ == "__main__":
    main()

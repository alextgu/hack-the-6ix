"""Commit → booking picker.

Takes raw Stay22 results and makes ONE decisive pick + a couple of
alternates. Never constructs booking URLs — always uses the Allez-wrapped
url/link fields Stay22 already returns (they carry STAY22_AID if we set
it before the query).

Not wired to health or brain. Called only from bot.py::cmd_commit.
"""
from __future__ import annotations
from typing import Optional


# ─── helpers ────────────────────────────────────────────────────────────────
def _cheapest_supplier(suppliers: dict) -> tuple[Optional[str], Optional[float]]:
    """Return (name, price_total) of the cheapest quoting supplier for this
    property, or (None, None) if no supplier priced it."""
    best_name: Optional[str] = None
    best_price: Optional[float] = None
    for name, s in (suppliers or {}).items():
        p = (s.get("price") or {}).get("total")
        if p is None:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if best_price is None or p < best_price:
            best_name, best_price = name, p
    return best_name, best_price


def _rating(r: dict) -> float:
    v = (r.get("rating") or {}).get("value")
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rank(
    results: list[dict],
    budget_per_person: Optional[int],
    guests: int,
    nights: int,
) -> tuple[list[dict], list[dict]]:
    """Return (within_budget_ranked, all_ranked_by_price) — each item is
    {result, supplier_name, price_total, rating}."""
    max_total: Optional[float] = None
    if budget_per_person and guests and nights:
        max_total = float(budget_per_person) * int(guests) * int(nights)

    within: list[dict] = []
    everything: list[dict] = []

    for r in results:
        supplier_name, price = _cheapest_supplier(r.get("suppliers") or {})
        if supplier_name is None or price is None:
            continue
        row = {
            "result": r,
            "supplier_name": supplier_name,
            "price_total": price,
            "rating": _rating(r),
        }
        everything.append(row)
        if max_total is None or price <= max_total:
            within.append(row)

    # in-budget: highest rating first, ties broken by lower price
    within.sort(key=lambda x: (-x["rating"], x["price_total"]))
    # fallback pool: cheapest first
    everything.sort(key=lambda x: x["price_total"])
    return within, everything


# ─── main API ──────────────────────────────────────────────────────────────
def pick_hotel(
    results: list[dict],
    budget_per_person: Optional[int],
    guests: int,
    nights: int,
) -> Optional[dict]:
    """From Stay22 `results`, return the single best-fit property.

    Rule: highest `rating.value` whose cheapest supplier total ≤
    budget × guests × nights. If nothing fits the budget, fall back to the
    cheapest available property regardless of rating (with a `fallback` flag).

    Returned dict:
      { result, supplier_name, price_total, rating, alternates: [<same shape>, ...], fallback? }
    `alternates` holds up to 2 next-best picks by the same rule so
    booking_options() can surface them without a second call.
    """
    if not results:
        return None

    within, everything = _rank(results, budget_per_person, guests, nights)

    if within:
        chosen = dict(within[0])
        chosen["alternates"] = [dict(x) for x in within[1:3]]
        return chosen

    if everything:
        chosen = dict(everything[0])
        chosen["alternates"] = [dict(x) for x in everything[1:3]]
        chosen["fallback"] = "cheapest_over_budget"
        return chosen

    return None


def booking_options(chosen: dict) -> Optional[dict]:
    """Pull Allez-wrapped URLs straight from the Stay22 response — never
    construct booking URLs manually. STAY22_AID (if set in env when the
    search ran) is already baked into these URLs by Stay22.

    Returns:
      { name, price_total, book_url, rating, supplier, alternates: [{name, price_total, book_url}, ...] }
    """
    if not chosen:
        return None

    r = chosen["result"]
    supplier_name = chosen["supplier_name"]
    supplier = (r.get("suppliers") or {}).get(supplier_name) or {}
    # prefer per-supplier link (routes to the exact OTA), fall back to
    # the top-level Stay22 Allez wrapper.
    book_url = supplier.get("link") or r.get("url") or ""

    alternates: list[dict] = []
    for alt in (chosen.get("alternates") or []):
        ar = alt["result"]
        a_supplier = (ar.get("suppliers") or {}).get(alt["supplier_name"]) or {}
        alternates.append({
            "name": ar.get("name") or "Hotel",
            "price_total": alt["price_total"],
            "book_url": a_supplier.get("link") or ar.get("url") or "",
        })

    return {
        "name": r.get("name") or "Hotel",
        "price_total": chosen["price_total"],
        "book_url": book_url,
        "rating": chosen.get("rating"),
        "supplier": supplier_name,
        "alternates": alternates,
        "fallback": chosen.get("fallback"),
    }

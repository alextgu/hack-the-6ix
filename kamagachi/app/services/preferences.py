"""Preference vectors — lightweight embeddings that rank a deck to a group.

MongoDB Atlas Vector Search is the target; this module returns simple 32-dim
float vectors so the same code path works with either Atlas $vectorSearch
or the in-memory cosine ranker used in the demo.
"""
from __future__ import annotations
import hashlib
import math
from typing import Sequence

from ..models.schemas import DeckHotel


VEC_DIM = 32


def _hash_to_unit(text: str, dim: int = VEC_DIM) -> list[float]:
    """Deterministic 32-dim unit vector from a text seed."""
    v = [0.0] * dim
    for i, chunk in enumerate([text[i:i+8] for i in range(0, max(1, len(text)), 8)][:dim]):
        h = int(hashlib.md5(chunk.encode()).hexdigest(), 16)
        v[i % dim] += (h % 1000) / 1000.0 - 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def hotel_embedding(h: DeckHotel) -> list[float]:
    """Embedding seed from name + tags + city + rough price bucket."""
    price_bucket = "budget" if h.price_per_night < 150 else "mid" if h.price_per_night < 350 else "lux"
    seed = " ".join([h.name, h.city, price_bucket, *h.tags])
    return _hash_to_unit(seed)


def preference_vector_from_chat(text: str) -> list[float]:
    return _hash_to_unit(text)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # inputs are unit-normalized


def rank_deck(hotels: list[DeckHotel], pref: list[float]) -> list[DeckHotel]:
    scored = []
    for h in hotels:
        emb = h.preference_embedding or hotel_embedding(h)
        scored.append((cosine(emb, pref), h))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [h for _, h in scored]

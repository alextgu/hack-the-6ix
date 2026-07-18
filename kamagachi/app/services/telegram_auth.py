"""HMAC-SHA-256 verification of Telegram Mini App initData.

Per Telegram spec:
  secret_key = HMAC_SHA256(bot_token, "WebAppData")
  data_check_string = sorted "key=value" of every field except `hash`, joined by \n
  expected_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest()
"""
from __future__ import annotations
import hmac
import hashlib
import json
from typing import Optional
from urllib.parse import parse_qsl

from ..models.schemas import MiniAppInitData, TelegramWebAppUser


def parse_and_verify(init_data: str, bot_token: str) -> Optional[MiniAppInitData]:
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        return None
    provided_hash = pairs.pop("hash", None)
    if not provided_hash:
        return None
    data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided_hash):
        return None

    user_obj: Optional[TelegramWebAppUser] = None
    if pairs.get("user"):
        try:
            user_obj = TelegramWebAppUser(**json.loads(pairs["user"]))
        except Exception:
            user_obj = None
    return MiniAppInitData(
        query_id=pairs.get("query_id"),
        user=user_obj,
        auth_date=int(pairs.get("auth_date", "0")),
        hash=provided_hash,
        raw=init_data,
        chat_instance=pairs.get("chat_instance"),
        chat_type=pairs.get("chat_type"),
        start_param=pairs.get("start_param"),
    )

"""Run the bot polling + FastAPI face server in ONE asyncio event loop.

Both processes share the in-memory `state._GROUPS` module singleton, so the
Mini App always reads what the bot most-recently wrote — no IPC needed.

Usage:
  python run.py                          # binds 0.0.0.0:8000
  PORT=8765 python run.py                # override port
  PUBLIC_WEBAPP_URL=https://xxx.trycloudflare.com python run.py
"""
from __future__ import annotations
import asyncio
import contextlib
import logging
import os
import signal

import uvicorn
from dotenv import load_dotenv
from telegram import Update

from app.bot import bot   # keep the bot.py logic untouched — just call build_app()
from app.api.api import app as fastapi_app


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("trippet.run")


async def _run_bot() -> None:
    """Initialize + start polling without .run_polling() (which owns its own loop).

    Wrapped in a retry loop so a transient Telegram TimedOut on startup doesn't
    take the whole process down. Once started, the updater's internal loop
    handles its own retries.

    No TELEGRAM_BOT_TOKEN → API-only mode: the Mini App + cards still serve,
    and the bot joins on the next deploy once the env var is set."""
    global _live_bot
    if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        log.warning("TELEGRAM_BOT_TOKEN not set — running API-only (no Telegram polling)")
        await asyncio.Event().wait()
    while True:
        app = bot.build_app()
        _live_bot = app.bot
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                bootstrap_retries=-1,     # infinite retries during startup
                drop_pending_updates=True,
            )
            log.info("bot: polling started")
            await asyncio.Event().wait()  # block until cancelled
        except asyncio.CancelledError:
            log.info("bot: cancelled, shutting down")
            with contextlib.suppress(Exception):
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            raise
        except Exception as e:
            log.warning("bot: crashed (%s: %s) — restarting in 5s", type(e).__name__, e)
            with contextlib.suppress(Exception):
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            await asyncio.sleep(5)


async def _heartbeat(get_bot) -> None:
    """Every 10 min: for recently-active chats that have gone quiet, let the
    supervisor decide whether Tabi should initiate. The pet is not passive."""
    from app.integrations import db
    from app.agents import supervisor
    from app.bot import bot as botmod
    from datetime import datetime, timezone

    HEARTBEAT_EVERY_S = 600
    while True:
        await asyncio.sleep(HEARTBEAT_EVERY_S)
        try:
            tg_bot = get_bot()
            if tg_bot is None:
                continue
            for chat_id in await asyncio.to_thread(db.active_chats, 72):
                last = await asyncio.to_thread(db.last_message_at, chat_id)
                if last:
                    quiet_s = (datetime.now(timezone.utc)
                               - datetime.fromisoformat(last)).total_seconds()
                    if quiet_s < supervisor.HEARTBEAT_SILENCE_S:
                        continue
                d = await asyncio.to_thread(supervisor.run_turn, chat_id, "heartbeat")
                if d.send:
                    class _Ctx:  # minimal ContextTypes shim for execute_decision
                        bot = tg_bot
                    await botmod.execute_decision(chat_id, d, _Ctx())
        except Exception as e:
            log.warning("heartbeat error: %s", e)


async def _run_api(port: int) -> None:
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    log.info("api: serving on 0.0.0.0:%d", port)
    await server.serve()


_live_bot = None  # set by _run_bot once polling is up; heartbeat reads it


async def _main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    tasks = [
        asyncio.create_task(_run_bot(), name="bot"),
        asyncio.create_task(_run_api(port), name="api"),
        asyncio.create_task(_heartbeat(lambda: _live_bot), name="heartbeat"),
    ]

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # windows

    await asyncio.wait([*tasks, asyncio.create_task(stop.wait())],
                       return_when=asyncio.FIRST_COMPLETED)
    for t in tasks:
        if not t.done():
            t.cancel()
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception) as e:
            if not isinstance(e, asyncio.CancelledError):
                log.exception("task exit: %s", e)


if __name__ == "__main__":
    asyncio.run(_main())

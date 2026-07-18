"""Seed a demo trip so the mini app is walkable without a real Telegram chat.

Usage:
  python -m kamagachi.scripts.seed_demo
Then open: http://localhost:8000/miniapp/?chat_id=demo-chat
"""
import asyncio
import httpx


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as c:
        r = await c.post("/api/seed", params={"chat_id": "demo-chat"})
        print(r.status_code, r.json())


if __name__ == "__main__":
    asyncio.run(main())

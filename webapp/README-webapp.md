# trippet — Telegram Mini App

Vanilla JS mini app served by the FastAPI backend.

## Local test

1. Start the FastAPI server (the one serving `/` and `/api/state/{group_id}`).
2. Open in a browser: `http://localhost:PORT/?group=demo-chat`
   - The `?group=` param is REQUIRED. Without it the app renders an error and stops.
   - Outside Telegram, the SDK is absent and the UI falls back to defaults — this is expected.
3. In-Telegram: launch via the bot's Web App button. Telegram injects `initData` and theme params automatically.

The app polls `GET /api/state/{group_id}` every 3s and swaps Lottie animations only when `pet.mood` changes.

## REPLACE THESE — designer note

The files in `webapp/animations/*.json` are **PLACEHOLDER Lottie animations** (breathing blobs with rough face features). Each file's meta `"nm"` field is tagged `trippet-<mood>-PLACEHOLDER`. Swap in real Bodymovin exports before shipping — same filenames (`happy.json`, `worried.json`, `sick.json`, `dying.json`, `graduated.json`), same 320x320 canvas.

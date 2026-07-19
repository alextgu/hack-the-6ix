# Deploying trippet to Google Cloud Run

> **Current deployment (2026-07-19):** project `hackthe6ix-502813`, region
> `us-central1`, service `trippet` →
> **https://trippet-69987838202.us-central1.run.app**
> Fully live — the bot polls Telegram and the Mini App serves. All runtime env
> vars are set ON THE SERVICE and persist across deploys: `TELEGRAM_BOT_TOKEN`,
> `GEMINI_API_KEY`/`GEMINI_MODEL`, `MONGODB_URI`/`MONGODB_DB`, `STAY22_API_KEY`/
> `STAY22_AID`, `ELEVENLABS_API_KEY`/`ELEVENLABS_VOICE_ID`, `PUBLIC_WEBAPP_URL`.
> Check them with:
> `gcloud run services describe trippet --region us-central1 --format="value(spec.template.spec.containers[0].env)"`
>
> Optional and NOT set: `AMADEUS_CLIENT_ID`/`AMADEUS_CLIENT_SECRET`. Without
> them `flights.py` serves bundled offers — carbon math is local either way,
> so the green lane is fully functional without them.
>
> Expect a burst of `409 Conflict` in the logs for ~30s during every deploy:
> the old revision is still polling while the new one starts. `run.py`'s
> supervisor loop recovers on its own — no action needed.

One container runs both the polling Telegram bot and the FastAPI Mini App
server (`run.py`). They share in-memory state, and Telegram allows only one
poller per bot token — so the service MUST run as **exactly one always-on
instance**. The flags below are not optional.

## One-time setup

1. Install the gcloud CLI: https://cloud.google.com/sdk/docs/install
   (Windows installer; then restart the terminal.)
2. `gcloud auth login`
3. Create a project + enable billing (the $300 free trial covers this easily;
   an always-on min-instance costs roughly $0.50/day for the weekend):
   ```
   gcloud projects create trippet-ht6 --set-as-default
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```
   (Billing: console.cloud.google.com → Billing → link the trial account.)

## Deploy (from the repo root)

```
gcloud run deploy trippet `
  --source . `
  --region us-central1 `
  --allow-unauthenticated `
  --min-instances 1 --max-instances 1 `
  --no-cpu-throttling `
  --memory 512Mi `
  --set-env-vars "TELEGRAM_BOT_TOKEN=<token>,GEMINI_API_KEY=<key>,MONGODB_URI=<uri>,MONGODB_DB=trippet"
```

`--source .` builds the Dockerfile with Cloud Build — no local Docker needed.

Then grab the service URL and tell the app about itself (the Mini App button
needs it):

```
$URL = gcloud run services describe trippet --region us-central1 --format 'value(status.url)'
gcloud run services update trippet --region us-central1 --update-env-vars "PUBLIC_WEBAPP_URL=$URL"
```

## Telegram wiring (once, in @BotFather)

- `/mybots` → your bot → Bot Settings → **Group Privacy → Turn off**
  (bot must see plain messages in groups)
- Bot Settings → **Configure Mini App** → set it to the `https://…run.app` URL
  (required for the deep-link buttons — `t.me/<bot>?startapp=…` — to open as
  a real Mini App; without it they fall back to the bot profile page)

## Sanity checks after deploy

- `https://<service-url>/api/health` → `{"ok": true}`
- `https://<service-url>/cards?group=1&name=You` → swipe deck in a browser
- `/start` in the Telegram group → pet hatches; type "map" → hotel deck button
- Cloud Run logs (console → Cloud Run → trippet → Logs): look for
  "bot: polling started" and "Mongo connected".

## Gotchas

- **Never scale above 1 instance** — a second poller makes Telegram return
  409 Conflict, and card sessions live in process memory (Mongo is a mirror,
  not a coordination layer).
- Redeploys restart the process; card sessions survive via Mongo
  (`db.load_session`), pet state currently doesn't (in-memory only).
- If the bot runs on Cloud Run, don't also run `python run.py` locally with
  the same token — same 409 Conflict. Use a second dev bot token locally.
- Newer GCP projects: if `--source` deploy fails with a storage 403, grant
  the default compute SA the builder role:
  `gcloud projects add-iam-policy-binding <project> --member=serviceAccount:<num>-compute@developer.gserviceaccount.com --role=roles/cloudbuild.builds.builder`

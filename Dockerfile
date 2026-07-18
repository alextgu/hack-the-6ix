# trippet — single container: Telegram bot (polling) + FastAPI Mini App server.
# run.py runs both in one asyncio loop sharing in-memory state, so this MUST
# deploy with exactly one instance (see DEPLOY.md: --min-instances=1
# --max-instances=1 --no-cpu-throttling).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT; run.py reads it (defaults to 8000 locally).
ENV PYTHONUNBUFFERED=1
CMD ["python", "run.py"]

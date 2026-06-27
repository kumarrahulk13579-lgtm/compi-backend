FROM python:3.12-slim

WORKDIR /app

COPY chat-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY db/ db/
COPY chat-service/ chat-service/

WORKDIR /app/chat-service
# Apply DB migrations on deploy (chat-service is the single migration owner — it ships alembic.ini),
# then start the API. alembic.ini lives at /app, so run the upgrade from there.
CMD ["sh", "-c", "cd /app && PYTHONPATH=/app alembic upgrade head && cd /app/chat-service && PYTHONPATH=/app uvicorn main:app --host ${UVICORN_HOST:-::} --port 8002"]

FROM python:3.12-slim

WORKDIR /app

COPY chat-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY db/ db/
COPY chat-service/ chat-service/

WORKDIR /app/chat-service
CMD ["sh", "-c", "PYTHONPATH=/app uvicorn main:app --host 0.0.0.0 --port 8002"]

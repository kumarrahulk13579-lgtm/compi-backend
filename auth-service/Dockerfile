FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY db/ db/
COPY auth-service/ auth-service/

WORKDIR /app/auth-service
CMD ["sh", "-c", "cd /app && PYTHONPATH=/app alembic upgrade head && cd /app/auth-service && uvicorn main:app --host 0.0.0.0 --port 8001"]

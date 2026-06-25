FROM python:3.12-slim

WORKDIR /app

COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db/ db/
COPY auth-service/ auth-service/

WORKDIR /app/auth-service
CMD ["sh", "-c", "PYTHONPATH=/app uvicorn main:app --host 0.0.0.0 --port 8001"]

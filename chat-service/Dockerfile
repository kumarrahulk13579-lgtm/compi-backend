FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db/ db/
COPY chat-service/ chat-service/

WORKDIR /app/chat-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

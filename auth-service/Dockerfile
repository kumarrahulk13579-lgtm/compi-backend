FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db/ db/
COPY auth-service/ auth-service/

WORKDIR /app/auth-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

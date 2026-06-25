FROM python:3.12-slim

WORKDIR /app

COPY gateway-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway-service/ gateway-service/

WORKDIR /app/gateway-service
CMD ["sh", "-c", "uvicorn main:app --host ${UVICORN_HOST:-::} --port 8000"]

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY excuse-ai-service.py .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 excuse-ai-service:app
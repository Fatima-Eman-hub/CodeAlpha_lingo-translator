FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

WORKDIR /app/backend

# Uses $PORT if the platform provides one (Back4app, Render, etc.), else defaults to 8080
EXPOSE 8080
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} app:app

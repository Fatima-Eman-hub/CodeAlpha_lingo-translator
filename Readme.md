# Lingo Translator

A simple translation web app with a Flask backend and a frontend interface.

## Project Structure

- frontend/: UI files
- backend/: Flask API and Python dependencies
- api/: Vercel serverless entry point
- public/: static files used by Vercel

## Run Locally

1. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Set a database URL:
   ```bash
   export DATABASE_URL="your-neon-connection-string"
   ```
3. Start the app:
   ```bash
   python app.py
   ```
4. Open http://127.0.0.1:5000

## Features

- Translate text between supported languages
- Auto-detect the source language
- Save recent translations and favorites
- Copy and speak translated text
- Deploy on Vercel or other hosts

## API Endpoints

- POST /api/translate
- GET /api/history?user_id=...
- POST /api/history
- PATCH /api/history/<id>
- DELETE /api/history/<id>
- GET /api/health

## Notes

- History is stored per browser using a client ID.
- The app uses the free Google Translate service through a Python library.

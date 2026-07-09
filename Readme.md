# Lingo Translator

A simple translation web app with a Flask backend and a frontend interface.

## Project Structure

```text
lingo-translator/
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/script.js
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── lingo.db
└── README.md
```

## Run Locally

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Features

- Translate text between supported languages
- Auto-detect the source language
- Save recent translations and favorites
- Copy and speak translated text
- Works as a single app with one server

## API Endpoints

- POST /api/translate
- GET /api/history?user_id=...
- POST /api/history
- PATCH /api/history/<id>
- DELETE /api/history/<id>
- GET /api/health

## Notes

- History is stored per browser using a local client ID.
- The app uses the free Google Translate service through a Python library.

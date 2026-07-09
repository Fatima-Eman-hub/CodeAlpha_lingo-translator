# Lingo — Language Translation Tool

## Project Structure
```
lingo-translator/
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/script.js
├── backend/
│   ├── app.py           → Flask server: translation API + per-user history API + serves the frontend
│   ├── requirements.txt
│   └── lingo.db          → SQLite database (auto-created on first run, gitignored)
└── README.md
```

## Run Locally (one server now — frontend is served by Flask itself)
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser. That's it — one terminal, one URL, both the UI and the API come from the same place. `lingo.db` is created automatically the first time it runs.

## How Translation Works
`frontend/js/script.js` → `POST /api/translate` → `backend/app.py` → `deep-translator` (Google Translate, free, no API key) → response back to frontend.

`backend/app.py` also auto-detects the source language using `langdetect` when "Detect language" is selected.

## How Per-User History Works (no login needed)
Every browser that opens the app generates one random ID with `crypto.randomUUID()` the first time, stored in that browser's `localStorage` (`lingo_client_id`). This ID is sent with every history request, and the backend scopes all reads/writes to it in the `history` table (SQLite).

Practical effect:
- Your history/favorites persist across refreshes and browser restarts (stored server-side, not just in memory)
- Two different people using the app (from different browsers/devices) never see each other's history
- It's tied to a *browser*, not a real account — clearing browser data or opening the site in a different browser starts a fresh history. If you want real accounts (same history across devices), that needs a login system, which is a bigger addition than this project currently has.

**API endpoints added for this:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/history?user_id=...` | fetch a user's last 50 translations |
| POST | `/api/history` | save a new translation to history |
| PATCH | `/api/history/<id>` | toggle favorite on one entry |
| DELETE | `/api/history/<id>` | delete one entry |

## Error Handling
- Empty input, text over 2000 characters, malformed JSON, unsupported language codes → all return clear `400` errors instead of crashing
- Google Translate outages / network issues → `502` with a friendly message, frontend shows a toast
- Same source/target language selected → skips the API call, returns the text unchanged instantly
- History endpoints validate `user_id` shape and reject cross-user access attempts (a user can only favorite/delete their own rows)

## Deploy (get a real public link)

We use **Render.com** — it has a genuinely free tier, deploys straight from GitHub, and needs no server management. The whole app (UI + API) is one Flask service, so it's one deployment.

**1. Push this project to GitHub** (a new repo, this whole `lingo-translator` folder).

**2. On [render.com](https://render.com):**
- Sign up (free, GitHub login works)
- **New +** → **Web Service** → connect your GitHub repo
- Settings:
  - **Root Directory:** leave blank (repo root)
  - **Build Command:** `pip install -r backend/requirements.txt`
  - **Start Command:** `cd backend && gunicorn app:app`
  - **Instance Type:** Free
- Click **Create Web Service**

Render builds it and gives you a public URL like `https://lingo-translator-xxxx.onrender.com` — that's the link you share. Opens in any browser, any device, works like a real hosted app.

**Free tier notes (be upfront about these when you demo/submit):**
- The free instance **sleeps after ~15 min of no traffic** and takes 30-60 seconds to wake up on the next visit — the first request after idle will feel slow, that's normal, not a bug.
- SQLite (`lingo.db`) lives on Render's disk, which is **not permanent on the free tier** — a redeploy or restart can wipe it. Fine for a demo/submission; for something you'd keep long-term, you'd eventually move to Render's free PostgreSQL instead of SQLite.
- Google Translate via `deep-translator` is unofficial/free and can occasionally rate-limit under heavy shared traffic — acceptable for a class project, not for real production scale.

## Known limitations
- No alternative translations or phonetic/romanized output (Google Translate free tier doesn't provide these)
- Uses the **unofficial free** Google Translate endpoint via `deep-translator` — fine for a student project/demo, not meant for production traffic.
- Text-to-speech (🔊 button) depends on voices installed on your OS/browser. If a language has no matching voice on your device, you'll get a toast saying so instead of silence.
- History is per-browser (via `localStorage` + SQLite), not per real account — see above.
- On Render's free tier, history may reset on redeploy/restart (see Deploy section).

## Features Implemented
- Language selector with search + flags, auto-detect
- Split view (responsive: stacks on mobile)
- Char/word counter, skeleton loader, toast notifications
- Copy, text-to-speech (browser native)
- Server-persisted, per-user translation history with favorites
- Keyboard shortcuts: `Ctrl+Enter` translate, `Ctrl+K` clear
- Deployable as a single public URL (frontend + backend unified)

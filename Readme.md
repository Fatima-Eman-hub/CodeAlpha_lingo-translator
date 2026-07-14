# Lingo — Language Translation Tool

## Project Structure
```
lingo-translator/
├── frontend/              → source of truth for the UI
│   ├── index.html
│   ├── css/style.css
│   └── js/script.js
├── public/                → mirror of frontend/, used only by Vercel's static hosting
├── backend/
│   ├── app.py              → Flask server: translation API + per-user history API + serves the frontend locally
│   └── requirements.txt
├── api/
│   └── index.py            → thin entry point Vercel uses to run backend/app.py as a serverless function
├── vercel.json             → routes /api/* to api/index.py, everything else served from /public
├── Dockerfile              → for Docker-based hosts (Back4app, etc.) as an alternative to Vercel
└── README.md
```

Two frontend copies (`frontend/` and `public/`) exist because Vercel expects static files in a conventional folder it serves directly via CDN, while `frontend/` remains what Flask serves when you run the app locally or on a traditional host (Render/Back4app/your own server). If you edit the UI, **edit both** (or copy one over the other) so they don't drift.

## Database: Postgres (Neon — free, no credit card)

This app stores per-user translation history in Postgres rather than a local file, specifically so it can run on serverless hosts like Vercel (which don't have persistent local disk).

**One-time setup:**
1. Go to [neon.tech](https://neon.tech) → sign up (no card required) → **Create a project**
2. Neon gives you a connection string that looks like:
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
3. Copy it — you'll set it as `DATABASE_URL` both locally and on whichever host you deploy to (same database works everywhere, so your history is the same no matter where the app runs).

The `history` table is created automatically the first time the app starts with a valid `DATABASE_URL` — no manual schema setup needed.

## Run Locally

**Windows (PowerShell):**
```powershell
cd backend
pip install -r requirements.txt
$env:DATABASE_URL="paste-your-neon-connection-string-here"
python app.py
```

**Mac/Linux:**
```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL="paste-your-neon-connection-string-here"
python app.py
```

Open **http://127.0.0.1:5000**. One terminal, one URL — Flask serves both the UI and the API.

> Without `DATABASE_URL` set, translation still works fine; only the history/favorites endpoints will return a clear error explaining what's missing, instead of crashing.

## How Translation Works
`frontend/js/script.js` → `POST /api/translate` → `backend/app.py` → `deep-translator` (Google Translate, free, no API key) → response back to frontend.

`backend/app.py` also auto-detects the source language using `langdetect` when "Detect language" is selected, and can name over 60 detected languages even though only 14 are selectable as translation targets.

## How Per-User History Works (no login needed)
Every browser that opens the app generates one random ID with `crypto.randomUUID()` the first time, stored in that browser's `localStorage` (`lingo_client_id`). This ID is sent with every history request, and the backend scopes all reads/writes to it in Postgres.

Practical effect:
- Your history/favorites persist permanently (Neon's free tier doesn't expire data, unlike some hosts' ephemeral disks)
- Two different people using the app (from different browsers/devices) never see each other's history
- It's tied to a *browser*, not a real account — clearing browser data or opening the site in a different browser starts a fresh history

**API endpoints:**
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
- Every unhandled error returns JSON (never Flask's default HTML error page), since the frontend always expects JSON from `/api/*`

## Deploy to Vercel (get a real public link)

**1. Set up Neon** (see "Database" section above) and copy your `DATABASE_URL`.

**2. Push this project to GitHub** (the whole `lingo-translator` folder, including `api/`, `public/`, and `vercel.json`).

**3. On [vercel.com](https://vercel.com):**
- Sign up (free, GitHub login works, no card required for hobby/free projects)
- **Add New** → **Project** → import your GitHub repo
- Vercel auto-detects the Python function in `api/` — you don't need to set a build/start command manually
- Before deploying, open **Environment Variables** and add:
  - **Key:** `DATABASE_URL`
  - **Value:** your Neon connection string
- Click **Deploy**

Vercel builds it and gives you a public URL like `https://lingo-translator-xxxx.vercel.app` — share that link with anyone.

**Why this works on Vercel when the old SQLite version didn't:** Vercel runs your backend as a *serverless function* — a fresh, temporary environment on every request, with no persistent local disk. SQLite is a file on disk, so it couldn't survive between requests there. Postgres (Neon) lives outside Vercel entirely, reached over the network, so it works the same way whether the request came from a serverless function, a traditional server, or your own laptop.

### Alternative hosts (same code, no changes needed)
Because the database is now external (Neon) instead of a local file, this same project also deploys cleanly to traditional hosts if you prefer one of those instead of Vercel:
- **Render.com** — Build Command: `pip install -r backend/requirements.txt`, Start Command: `cd backend && gunicorn app:app`, set `DATABASE_URL` in its Environment settings.
- **Back4app Containers** — uses the included `Dockerfile`, free tier with no credit card required, set `DATABASE_URL` in its environment settings.

All three (Vercel, Render, Back4app) can even point at the **same** Neon database if you want — history stays consistent no matter which you use.

## Known limitations
- No alternative translations or phonetic/romanized output (Google Translate free tier doesn't provide these)
- Uses the **unofficial free** Google Translate endpoint via `deep-translator` — fine for a student project/demo, not meant for production traffic.
- Text-to-speech (🔊 button) depends on voices installed on your OS/browser. If a language has no matching voice on your device, you'll get a toast saying so instead of silence.
- History is per-browser (via `localStorage` + a `client_id`), not per real account.
- Neon's free tier has a monthly compute-hour budget; an idle app uses effectively none of it (compute scales to zero after 5 minutes of inactivity), so this comfortably covers a demo/class project.

## Features Implemented
- Language selector with search + flags, auto-detect (60+ languages recognized for detection, 14 selectable as targets)
- Split view (responsive: stacks on mobile)
- Char/word counter (CJK-aware), skeleton loader, toast notifications
- Copy, text-to-speech (browser native, locale-matched voices)
- Text size control (A-/A+) and a contrast/dark-mode toggle
- Server-persisted, per-user translation history with favorites, searchable in a slide-in drawer
- Keyboard shortcuts: `Ctrl+Enter` translate, `Ctrl+K` clear
- Deployable as a single public URL on Vercel, Render, or Back4app — same codebase, no changes needed

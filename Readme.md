# Lingo Translator

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
│   ├── requirements.txt
│   ├── requirements-dev.txt → adds pytest, for running tests
│   └── tests/
│       └── test_app.py     → 25 automated tests (mocked, no live DB/internet needed)
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
`frontend/js/script.js` → `POST /api/translate` → `backend/app.py` → checks an in-memory cache first → if not cached, `deep-translator` (Google Translate, free, no API key) → response back to frontend.

`backend/app.py` also auto-detects the source language using `langdetect` when "Detect language" is selected, and can name over 60 detected languages even though only 14 are selectable as translation targets.

### Caching
Identical requests (same text + source + target) are cached in memory for the life of the running process, so a repeated translation returns instantly without calling Google Translate again. Two honest caveats: it resets on every process restart, and on a serverless host (Vercel) it's per-instance rather than globally shared — still useful, just not a guarantee. Good enough for a student project; a shared cache (e.g. Redis) would be the production-grade upgrade.

### Fallback provider
If Google Translate fails, the backend automatically retries the same request through MyMemory (also free, no API key) before giving up. Only if *both* fail does the request return a `502`. This is tested directly (`test_translate_falls_back_to_mymemory_when_google_fails`).

### Rate limiting
`/api/translate` is limited to 30 requests/minute per IP; the history endpoints to 60/minute. Exceeding it returns a proper `429 Too Many Requests` with a JSON body (not a crash, not an HTML page). Uses `flask-limiter` with in-memory storage — like the cache, this is per-instance on serverless hosts rather than globally enforced, which is an accepted trade-off for this project's scale.

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
- Google Translate outages → automatic fallback to MyMemory; only a `502` if both are down, with a friendly message and a frontend toast
- Same source/target language selected → skips the API call, returns the text unchanged instantly
- More than 30 translation requests/minute from one IP → `429 Too Many Requests`, not a crash
- History endpoints validate `user_id` shape and reject cross-user access attempts (a user can only favorite/delete their own rows)
- Every unhandled error returns JSON with the correct status code (never Flask's default HTML error page), since the frontend always expects JSON from `/api/*`

## Testing

25 automated tests cover the backend's routing, validation, error handling, caching, and fallback behavior (`backend/tests/test_app.py`). They mock Google Translate, MyMemory, and the database, so they run in well under a second, need no internet connection, and need no live Neon database configured.

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

What's covered: input validation on every endpoint (empty/oversized text, invalid language codes, malformed JSON), the same-source-equals-target shortcut, translation success/failure/empty-result handling, auto-detection, full history CRUD (get/save/favorite/delete), and — importantly — that a user can never read or modify another user's history row (the ownership check is tested directly).

What's intentionally *not* covered: real network calls to Google Translate, and real queries against Postgres — those are mocked on purpose, so the test suite verifies *this project's own logic*, not a third-party service's uptime.

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

Vercel builds it and gives you a public URL like 'https://lingo-translator-umber.vercel.app/' — share that link with anyone.

**Why this works on Vercel when the old SQLite version didn't:** Vercel runs your backend as a *serverless function* — a fresh, temporary environment on every request, with no persistent local disk. SQLite is a file on disk, so it couldn't survive between requests there. Postgres (Neon) lives outside Vercel entirely, reached over the network, so it works the same way whether the request came from a serverless function, a traditional server, or your own laptop.

### Alternative hosts (same code, no changes needed)
Because the database is now external (Neon) instead of a local file, this same project also deploys cleanly to traditional hosts if you prefer one of those instead of Vercel:
- **Render.com** — Build Command: `pip install -r backend/requirements.txt`, Start Command: `cd backend && gunicorn app:app`, set `DATABASE_URL` in its Environment settings.
- **Back4app Containers** — uses the included `Dockerfile`, free tier with no credit card required, set `DATABASE_URL` in its environment settings.

All three (Vercel, Render, Back4app) can even point at the **same** Neon database if you want — history stays consistent no matter which you use.

## Known limitations
- No alternative translations or phonetic/romanized output (Google Translate free tier doesn't provide these)
- Uses **unofficial free** endpoints (Google Translate + MyMemory fallback) via `deep-translator` — fine for a student project/demo, not meant for large-scale production traffic.
- Text-to-speech (🔊 button) depends on voices installed on your OS/browser. If a language has no matching voice on your device, you'll get a toast saying so instead of silence.
- History is per-browser (via `localStorage` + a `client_id`), not per real account.
- Neon's free tier has a monthly compute-hour budget; an idle app uses effectively none of it (compute scales to zero after 5 minutes of inactivity), so this comfortably covers a demo/class project.
- The translation cache and rate limiter are both in-memory — correct and useful on a single running instance (local, Render, Back4app), but not perfectly globally enforced across multiple serverless instances on Vercel. A Redis-backed version of both would be the production upgrade.
- No BLEU/ROUGE-style translation quality metric — those require a reference ("known correct") translation corpus to score against, which doesn't exist here; this is more of an ML-model-evaluation concept than something applicable to a live API-wrapper app. A more fitting quality signal for this kind of app would be user feedback (👍/👎 per translation), not yet implemented.

## Features Implemented
- Language selector with search + flags, auto-detect (60+ languages recognized for detection, 14 selectable as targets)
- Split view (responsive: stacks on mobile)
- Char/word counter (CJK-aware), skeleton loader, toast notifications
- Copy, text-to-speech (browser native, locale-matched voices)
- Text size control (A-/A+) and a contrast/dark-mode toggle
- Server-persisted, per-user translation history with favorites, searchable in a slide-in drawer
- Keyboard shortcuts: `Ctrl+Enter` translate, `Ctrl+K` clear
- Response caching, automatic fallback translation provider, and per-IP rate limiting for resilience
- 25 automated tests covering routing, validation, caching, fallback, and access control
- Deployable as a single public URL on Vercel, Render, or Back4app — same codebase, no changes needed
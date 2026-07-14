"""Flask backend for the Lingo translator app."""

import os
import time

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


@app.route("/")
def index():
    return app.send_static_file("index.html")


MAX_TEXT_LENGTH = 2000  # mirrors the frontend's maxlength on the textarea
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

LANG_MAP = {
    "en": ("en", "English"),
    "ur": ("ur", "Urdu"),
    "es": ("es", "Spanish"),
    "fr": ("fr", "French"),
    "de": ("de", "German"),
    "ar": ("ar", "Arabic"),
    "zh": ("zh-CN", "Chinese"),
    "ja": ("ja", "Japanese"),
    "hi": ("hi", "Hindi"),
    "ru": ("ru", "Russian"),
    "pt": ("pt", "Portuguese"),
    "tr": ("tr", "Turkish"),
    "ko": ("ko", "Korean"),
    "it": ("it", "Italian"),
}
DETECT_NORMALIZE = {"zh-cn": "zh", "zh-tw": "zh"}

DETECT_LANGUAGE_NAMES = {
    "en": "English", "ur": "Urdu", "es": "Spanish", "fr": "French", "de": "German",
    "ar": "Arabic", "zh": "Chinese", "ja": "Japanese", "hi": "Hindi", "ru": "Russian",
    "pt": "Portuguese", "tr": "Turkish", "ko": "Korean", "it": "Italian",
    "fa": "Persian", "nl": "Dutch", "pl": "Polish", "sv": "Swedish", "fi": "Finnish",
    "no": "Norwegian", "da": "Danish", "el": "Greek", "he": "Hebrew", "th": "Thai",
    "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay", "cs": "Czech", "sk": "Slovak",
    "ro": "Romanian", "hu": "Hungarian", "bg": "Bulgarian", "uk": "Ukrainian",
    "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "gu": "Gujarati",
    "pa": "Punjabi", "sw": "Swahili", "af": "Afrikaans", "sq": "Albanian", "am": "Amharic",
    "hy": "Armenian", "az": "Azerbaijani", "eu": "Basque", "be": "Belarusian",
    "ca": "Catalan", "hr": "Croatian", "et": "Estonian", "gl": "Galician",
    "ka": "Georgian", "is": "Icelandic", "kn": "Kannada", "kk": "Kazakh",
    "lv": "Latvian", "lt": "Lithuanian", "mk": "Macedonian", "mn": "Mongolian",
    "ne": "Nepali", "sr": "Serbian", "sl": "Slovenian", "so": "Somali",
    "tl": "Filipino", "cy": "Welsh", "km": "Khmer", "lo": "Lao", "my": "Burmese",
    "si": "Sinhala",
}


def get_db():
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Create a free Postgres database at "
                "https://neon.tech, then set DATABASE_URL to its connection string."
            )
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if not DATABASE_URL:
        return
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_code TEXT NOT NULL,
            target_code TEXT NOT NULL,
            src_text TEXT NOT NULL,
            tgt_text TEXT NOT NULL,
            favorited BOOLEAN NOT NULL DEFAULT FALSE,
            created_at DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)")
    conn.commit()
    cur.close()
    conn.close()


init_db()


def is_valid_user_id(user_id):
    return isinstance(user_id, str) and 8 <= len(user_id) <= 100


@app.errorhandler(Exception)
def handle_any_error(e):
    app.logger.error(f"Unhandled error: {e}")
    message = str(e) if isinstance(e, RuntimeError) else "internal server error"
    return jsonify({"error": message}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "database_configured": bool(DATABASE_URL)})


@app.route("/api/translate", methods=["POST"])
def translate():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "request body must be valid JSON"}), 400

    text = (data.get("text") or "").strip()
    source = data.get("source", "auto")
    target = data.get("target", "en")

    if not text:
        return jsonify({"error": "text is required"}), 400

    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"text too long (max {MAX_TEXT_LENGTH} characters)"}), 400

    if not isinstance(target, str) or target not in LANG_MAP:
        return jsonify({"error": f"unsupported target language: {target}"}), 400

    if not isinstance(source, str):
        return jsonify({"error": "source must be a string"}), 400

    detected_language_name = ""

    if source == "auto":
        try:
            raw_code = detect(text)
            norm_code = DETECT_NORMALIZE.get(raw_code, raw_code)
            detected_language_name = DETECT_LANGUAGE_NAMES.get(norm_code, norm_code.upper())
            source_code = "auto"
        except LangDetectException:
            source_code = "auto"
    else:
        if source not in LANG_MAP:
            return jsonify({"error": f"unsupported source language: {source}"}), 400
        source_code = LANG_MAP[source][0]

    target_code = LANG_MAP[target][0]

    if source_code != "auto" and source_code == target_code:
        return jsonify({
            "translation": text,
            "detectedLanguage": detected_language_name,
            "phonetic": "",
            "alternatives": [],
        })

    try:
        translated = GoogleTranslator(source=source_code, target=target_code).translate(text)
    except Exception as e:
        app.logger.error(f"Translation failed: {e}")
        return jsonify({"error": "translation service is temporarily unavailable — please try again"}), 502

    if not translated:
        return jsonify({"error": "translation service returned an empty result — please try again"}), 502

    return jsonify({
        "translation": translated,
        "detectedLanguage": detected_language_name,
        "phonetic": "",
        "alternatives": [],
    })


@app.route("/api/history", methods=["GET"])
def get_history():
    user_id = request.args.get("user_id", "")
    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id query param is required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, source_code, target_code, src_text, tgt_text, favorited, created_at "
        "FROM history WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()

    return jsonify({"history": [dict(r) for r in rows]})


@app.route("/api/history", methods=["POST"])
def save_history():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "")

    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id is required"}), 400

    source_code = (data.get("source_code") or "").strip()
    target_code = (data.get("target_code") or "").strip()
    src_text = (data.get("src_text") or "").strip()
    tgt_text = (data.get("tgt_text") or "").strip()

    if not (source_code and target_code and src_text and tgt_text):
        return jsonify({"error": "source_code, target_code, src_text, tgt_text are all required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO history (user_id, source_code, target_code, src_text, tgt_text, favorited, created_at) "
        "VALUES (%s, %s, %s, %s, %s, FALSE, %s) RETURNING id",
        (user_id, source_code, target_code, src_text, tgt_text, time.time()),
    )
    new_id = cur.fetchone()["id"]
    db.commit()

    cur.execute(
        "DELETE FROM history WHERE user_id = %s AND id NOT IN "
        "(SELECT id FROM history WHERE user_id = %s ORDER BY created_at DESC LIMIT 50)",
        (user_id, user_id),
    )
    db.commit()
    cur.close()

    return jsonify({"id": new_id}), 201


@app.route("/api/history/<int:row_id>", methods=["PATCH"])
def toggle_favorite(row_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "")
    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id is required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, favorited FROM history WHERE id = %s AND user_id = %s", (row_id, user_id)
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        return jsonify({"error": "not found"}), 404

    new_val = not row["favorited"]
    cur.execute("UPDATE history SET favorited = %s WHERE id = %s", (new_val, row_id))
    db.commit()
    cur.close()
    return jsonify({"id": row_id, "favorited": bool(new_val)})


@app.route("/api/history/<int:row_id>", methods=["DELETE"])
def delete_history_row(row_id):
    user_id = request.args.get("user_id", "")
    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id query param is required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM history WHERE id = %s AND user_id = %s", (row_id, user_id))
    db.commit()
    cur.close()
    return jsonify({"deleted": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

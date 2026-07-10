"Backend file using Flask framework for a translation application. It includes routes for health check, translation, and managing translation history. The app uses SQLite for storing user translation history and supports multiple languages through the Google Translator API. It also handles CORS and serves a frontend from a specified directory."
import os
import sqlite3
import time

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


MAX_TEXT_LENGTH = 2000
DB_PATH = os.path.join(BASE_DIR, "lingo.db")

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


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            source_code TEXT NOT NULL,
            target_code TEXT NOT NULL,
            src_text TEXT NOT NULL,
            tgt_text TEXT NOT NULL,
            favorited INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)")
    conn.commit()
    conn.close()


init_db()


def is_valid_user_id(user_id):
    return isinstance(user_id, str) and 8 <= len(user_id) <= 100


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


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
            if norm_code in LANG_MAP:
                detected_language_name = LANG_MAP[norm_code][1]
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
    rows = db.execute(
        "SELECT id, source_code, target_code, src_text, tgt_text, favorited, created_at "
        "FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    ).fetchall()

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
    cur = db.execute(
        "INSERT INTO history (user_id, source_code, target_code, src_text, tgt_text, favorited, created_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?)",
        (user_id, source_code, target_code, src_text, tgt_text, time.time()),
    )
    db.commit()

    db.execute(
        "DELETE FROM history WHERE user_id = ? AND id NOT IN "
        "(SELECT id FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT 50)",
        (user_id, user_id),
    )
    db.commit()

    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/history/<int:row_id>", methods=["PATCH"])
def toggle_favorite(row_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "")
    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id is required"}), 400

    db = get_db()
    row = db.execute(
        "SELECT id, favorited FROM history WHERE id = ? AND user_id = ?", (row_id, user_id)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    new_val = 0 if row["favorited"] else 1
    db.execute("UPDATE history SET favorited = ? WHERE id = ?", (new_val, row_id))
    db.commit()
    return jsonify({"id": row_id, "favorited": bool(new_val)})


@app.route("/api/history/<int:row_id>", methods=["DELETE"])
def delete_history_row(row_id):
    user_id = request.args.get("user_id", "")
    if not is_valid_user_id(user_id):
        return jsonify({"error": "valid user_id query param is required"}), 400

    db = get_db()
    db.execute("DELETE FROM history WHERE id = ? AND user_id = ?", (row_id, user_id))
    db.commit()
    return jsonify({"deleted": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

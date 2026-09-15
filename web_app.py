"""Replit HTTP entry point. Serve only browser assets, never repository files."""
import os
import time
from collections import defaultdict, deque
from threading import Lock
from urllib.parse import urlparse
import requests
from flask import Flask, Response, jsonify, request, redirect
from werkzeug.exceptions import HTTPException
from web_assistant import reply, MAC_DOWNLOAD_URL

app = Flask(__name__, static_folder="web_static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 65536
visits = defaultdict(deque)
visit_lock = Lock()

@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'"
    return response

@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.get("/api/status")
def status():
    return jsonify(mac_download="/download/mac", tts_configured=bool(os.getenv("ELEVENLABS_API_KEY")), ready=True, ai_configured=bool(os.getenv("GEMINI_API_KEY")), weather_configured=bool(os.getenv("WEATHER_API")))

@app.get("/download/mac")
def download_mac():
    return redirect(MAC_DOWNLOAD_URL, code=302)

@app.post("/api/chat")
def chat():
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        return jsonify(error="Use Swift from its own browser tab."), 403
    if not request.is_json:
        return jsonify(error="Expected a JSON request."), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400
    message, history = data.get("message"), data.get("history", [])
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        return jsonify(error="Please enter between 1 and 4,000 characters."), 400
    if not isinstance(history, list) or len(history) > 20 or any(not isinstance(e, dict) or e.get("role") not in ("user", "model") or not isinstance(e.get("text"), str) or len(e["text"]) > 8000 for e in history):
        return jsonify(error="Conversation is too long. Start a new chat."), 400
    timezone = data.get("timezone", "UTC")
    if not isinstance(timezone, str) or len(timezone) > 100:
        return jsonify(error="Invalid timezone."), 400
    # Global process limit avoids trusting spoofable proxy/IP headers.
    with visit_lock:
        now = time.monotonic()
        recent = visits["all"]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 30:
            return jsonify(error="Swift is busy. Please try again in a minute."), 429
        recent.append(now)
    try:
        return jsonify(reply(message.strip(), history, timezone))
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in (401, 403):
            error = "Gemini rejected the key. Check GEMINI_API_KEY in Replit Secrets and restart."
        elif code == 429:
            error = "Gemini's usage limit has been reached. Try again later or check your Gemini quota."
        elif code == 404:
            error = "This Gemini model is unavailable. Set GEMINI_MODEL to a model supported by your key and restart."
        else:
            error = "The AI service couldn't respond. Please try again shortly."
        # Never return or log exception strings: provider URLs may contain credentials.
        app.logger.warning("Assistant request failed (%s)", type(exc).__name__)
        return jsonify(error=error), 503

@app.post("/api/speech")
def speech():
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        return jsonify(error="Use Swift from its own browser tab."), 403
    data = request.get_json(silent=True)
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return jsonify(error="Speech requires 1 to 4,000 characters."), 400
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        return jsonify(error="ElevenLabs is not configured."), 503
    with visit_lock:
        now = time.monotonic()
        recent = visits["speech"]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 10:
            return jsonify(error="Speech limit reached. Try again in a minute."), 429
        recent.append(now)
    voice = os.getenv("ELEVENLABS_VOICE_ID", "dtSEyYGNJqjrtBArPCVZ")
    if not voice.isalnum():
        return jsonify(error="Invalid voice configuration."), 503
    try:
        result = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": key},
            params={"output_format": "mp3_44100_128"},
            json={"text": text.strip(), "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_v3")},
            timeout=(10, 60),
        )
        if result.status_code != 200:
            return jsonify(error="ElevenLabs could not generate speech. Check the key, voice access, and quota."), 503
        return Response(result.content, mimetype="audio/mpeg")
    except requests.RequestException:
        return jsonify(error="Speech service is temporarily unavailable."), 503

@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)

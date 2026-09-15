"""Spoken replies using ElevenLabs, with macOS speech as a fallback."""
import os
import subprocess
import tempfile
import threading
import time

import requests
from dotenv import load_dotenv
from runtime_paths import data_dir

DEFAULT_VOICE_ID = 'dtSEyYGNJqjrtBArPCVZ'
DEFAULT_MODEL_ID = 'eleven_v3'
_retry_after = 0.0

def _play(command, cancel):
    if cancel.is_set():
        return False
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while process.poll() is None:
        if cancel.wait(0.05):
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return False
    return process.returncode == 0

def speech(dialogue, cancel_event=None):
    global _retry_after
    cancel = cancel_event or threading.Event()
    if cancel.is_set():
        return False
    load_dotenv(data_dir() / '.env')
    key = os.getenv('ELEVENLABS_API_KEY')
    voice = os.getenv('ELEVENLABS_VOICE_ID', DEFAULT_VOICE_ID)
    if key and voice.isalnum() and time.monotonic() >= _retry_after:
        try:
            result = requests.post(
                f'https://api.elevenlabs.io/v1/text-to-speech/{voice}',
                headers={'xi-api-key': key}, params={'output_format': 'mp3_44100_128'},
                json={'text': dialogue[:4000], 'model_id': os.getenv('ELEVENLABS_MODEL_ID', DEFAULT_MODEL_ID)},
                timeout=(5, 12),
            )
            if cancel.is_set():
                return False
            if result.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix='.mp3') as audio:
                    audio.write(result.content)
                    audio.flush()
                    if _play(['/usr/bin/afplay', audio.name], cancel):
                        return True
            _retry_after = time.monotonic() + 300
        except requests.RequestException:
            _retry_after = time.monotonic() + 300
    return _play(['/usr/bin/say', '--', dialogue], cancel)

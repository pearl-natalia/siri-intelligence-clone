"""Local Whisper transcription with cancellable recording and cached models."""
import os
import threading
import time
from functools import lru_cache

from runtime_paths import data_dir

@lru_cache(maxsize=1)
def _models():
    import whisper
    from silero_vad import load_silero_vad
    cache = data_dir() / 'models' / 'whisper'
    cache.mkdir(parents=True, exist_ok=True)
    return whisper.load_model(os.getenv('WHISPER_MODEL', 'base.en'), download_root=str(cache)), load_silero_vad()

def transcribe(SILENCE_DURATION=1.2, START_TIMEOUT=10, VAD_THRESHOLD=0.35, cancel_event=None):
    import numpy as np
    import sounddevice as sd
    import torch
    cancel = cancel_event or threading.Event()
    if cancel.is_set():
        return None
    whisper_model, vad_model = _models()
    if cancel.is_set():
        return None
    vad_model.reset_states()
    rate, chunk = 16000, 512
    recorded = []
    started = time.monotonic()
    last_speech = None
    # Blocking reads keep VAD work out of PortAudio's real-time callback.
    with sd.InputStream(channels=1, samplerate=rate, blocksize=chunk, dtype='float32') as stream:
        while not cancel.is_set():
            audio, _ = stream.read(chunk)
            recorded.append(audio.copy())
            with torch.no_grad():
                probability = vad_model(torch.from_numpy(audio.flatten()), rate).item()
            now = time.monotonic()
            if probability > VAD_THRESHOLD:
                last_speech = now
            if last_speech is None and now - started >= START_TIMEOUT:
                return None
            if last_speech is not None and now - last_speech >= SILENCE_DURATION:
                break
            if now - started >= 45:
                break
    if cancel.is_set() or last_speech is None or not recorded:
        return None
    audio = np.concatenate(recorded).flatten().astype(np.float32)
    result = whisper_model.transcribe(audio, language='en', fp16=False)
    if cancel.is_set():
        return None
    text = result.get('text', '').strip()
    # Voice turns stay in memory; do not leave transcripts in the app bundle.
    return text or None

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_VOICE_ID = "dtSEyYGNJqjrtBArPCVZ"
DEFAULT_MODEL_ID = "eleven_v3"


def _say(dialogue: str) -> None:
    subprocess.run(["say", "-v", "Alex", dialogue], check=False)


def _elevenlabs(dialogue: str) -> bool:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)
    speed = float(os.getenv("ELEVENLABS_SPEED", "1.0"))
    stability = float(os.getenv("ELEVENLABS_STABILITY", "0.5"))
    similarity_boost = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75"))
    style = float(os.getenv("ELEVENLABS_STYLE", "0.0"))
    optimize_latency = os.getenv("ELEVENLABS_OPTIMIZE_LATENCY")

    if not api_key:
        print("ElevenLabs TTS skipped: ELEVENLABS_API_KEY or ELEVENLABS_API_KEY is missing.")
        return False

    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.play import play
        from elevenlabs.types.voice_settings import VoiceSettings

        client = ElevenLabs(api_key=api_key)
        request = {
            "text": dialogue,
            "voice_id": voice_id,
            "model_id": model_id,
            "output_format": "mp3_44100_128",
            "voice_settings": VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                speed=speed,
                use_speaker_boost=True,
            ),
        }
        if optimize_latency and model_id != "eleven_v3":
            request["optimize_streaming_latency"] = int(optimize_latency)
        audio = client.text_to_speech.convert(**request)
        play(audio)
        return True
    except Exception as exc:
        print(f"ElevenLabs TTS failed: {exc}")
        return False


def speech(dialogue):
    print("Brad: ", dialogue)
    if not _elevenlabs(dialogue):
        _say(dialogue)

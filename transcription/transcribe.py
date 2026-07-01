import whisper, time, threading, os, warnings
import sounddevice as sd
import numpy as np
import torch

def _load_vad():
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        trust_repo=True,
    )
    return model

def transcribe(SILENCE_DURATION=3, START_TIMEOUT=10, VAD_THRESHOLD=0.35):
    # Audio parameters — 512-sample chunks required by Silero VAD at 16kHz
    RATE = 16000
    CHANNELS = 1
    CHUNK = 512

    whisper_model = whisper.load_model("base")
    vad_model = _load_vad()
    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")
    recorded_audio = []
    started_at = time.time()
    last_speech_time = None
    heard_speech = False
    max_rms = 0.0
    max_speech_prob = 0.0

    running = True

    def audio_callback(indata, frames, time_info, status):
        nonlocal heard_speech, last_speech_time, max_rms, max_speech_prob
        if status:
            print(status)

        audio_chunk = indata.copy()
        recorded_audio.append(audio_chunk)
        rms = float(np.sqrt(np.mean(np.square(audio_chunk))))
        max_rms = max(max_rms, rms)

        # Run VAD on this 512-sample chunk
        tensor = torch.from_numpy(audio_chunk.flatten()).float()
        speech_prob = vad_model(tensor, RATE).item()
        max_speech_prob = max(max_speech_prob, speech_prob)
        if speech_prob > VAD_THRESHOLD:
            heard_speech = True
            last_speech_time = time.time()

    def silence_monitor():
        nonlocal running
        while running:
            now = time.time()
            if not heard_speech and now - started_at > START_TIMEOUT:
                print("No speech detected. Stopping recording...")
                running = False
            elif heard_speech and last_speech_time and now - last_speech_time > SILENCE_DURATION:
                print("Silence detected. Stopping recording...")
                running = False
            time.sleep(0.3)

    try:
        print("\nRecording... Speak into the mic. Press Ctrl+C to stop manually.")
        silence_thread = threading.Thread(target=silence_monitor)
        silence_thread.start()

        with sd.InputStream(callback=audio_callback, channels=CHANNELS, samplerate=RATE, blocksize=CHUNK):
            while running:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("Manual stop detected. Finishing up...")

    print(f"Audio debug: max_rms={max_rms:.5f}, max_speech_prob={max_speech_prob:.2f}")
    if not recorded_audio:
        print("No audio was captured. Check microphone permissions/input device.")
        return None

    full_recording = np.concatenate(recorded_audio, axis=0).flatten().astype(np.float32)
    if not heard_speech:
        print("No speech was detected. Check microphone permissions/input device or try speaking closer to the mic.")
        return None

    result = whisper_model.transcribe(full_recording, language='en')
    transcription = result["text"].strip()
    with open(os.path.join(os.path.dirname(__file__), "transcription.txt"), "w") as file:
        file.write(transcription + "\n")
        print("User: ", transcription)
    return transcription

if __name__ == "__main__":
    transcribe()

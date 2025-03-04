import whisper, time, threading
import sounddevice as sd
import numpy as np

def transcribe():
    # Audio parameters
    RATE = 16000
    CHANNELS = 1
    CHUNK = 1024
    SILENCE_THRESHOLD = 0.5
    SILENCE_DURATION = 3  # Seconds of silence to trigger stop
    
    model = whisper.load_model("base")
    recorded_audio = []
    last_sound_time = time.time()

    running = True  # Define running here inside the function

    def audio_callback(indata, frames, time_info, status):
        nonlocal last_sound_time  # Access the last_sound_time variable from the enclosing function
        if status:
            print(status)

        audio_chunk = indata.copy()
        recorded_audio.append(audio_chunk)

        volume_norm = np.linalg.norm(audio_chunk)  
        if volume_norm > SILENCE_THRESHOLD:
            last_sound_time = time.time()

    def silence_monitor():
        nonlocal running  # Access the running variable from the enclosing function
        while running:
            if time.time() - last_sound_time > SILENCE_DURATION:
                print("\nSilence detected. Stopping recording...")
                running = False
            time.sleep(0.5)

    try:
        print("Recording... Speak into the mic. Press Ctrl+C to stop manually.")
        silence_thread = threading.Thread(target=silence_monitor)
        silence_thread.start()

        with sd.InputStream(callback=audio_callback, channels=CHANNELS, samplerate=RATE, blocksize=CHUNK):
            while running:
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nManual stop detected. Finishing up...")

    # Concatenate all recorded audio chunks into a single array
    full_recording = np.concatenate(recorded_audio, axis=0).flatten().astype(np.float32)

    # Transcription
    print("Transcribing audio...")
    result = model.transcribe(full_recording, language='en')
    transcription = result["text"].strip()
    with open("transcription.txt", "w") as file:
        file.write(transcription + "\n")
    print("\nDone")

if __name__ == "__main__":
    transcribe()

import requests, os, pyaudio
from dotenv import load_dotenv
from pydub import AudioSegment

# def speech(dialogue):
#     # API
#     load_dotenv()
#     api_key = os.getenv("PLAYAI_API_KEY")
#     user_id = os.getenv("PLAYAI_USER_ID")
#     path = "transcription/response.wav"
#     if not api_key:
#         raise ValueError("API key is missing. Please check your .env file.")
#     if not user_id:
#         raise ValueError("User ID is missing. Please check your .env file.")

#     # Set up
#     headers = {
#         'Authorization': f'Bearer {api_key}',
#         'Content-Type': 'application/json',
#         'X-USER-ID': user_id  
#     }
#     json_data = {
#         'model': 'PlayDialog',
#         'text': dialogue,
#         'voice': 's3://voice-cloning-zero-shot/baf1ef41-36b6-428c-9bdf-50ba54682bd8/original/manifest.json',
#         'outputFormat': 'wav'
#     }

#     print(dialogue)
#     response = requests.post('https://api.play.ai/api/v1/tts/stream', headers=headers, json=json_data)
#     if response.status_code == 200:
#         with open(path, 'wb') as f:
#             f.write(response.content)
#     else:
#         print(f"Request failed with status code {response.status_code}: {response.text}")

#     audio = AudioSegment.from_wav(path)
#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16,
#                     channels=1,
#                     rate=audio.frame_rate,
#                     output=True)
#     for chunk in audio[::1024]:
#         stream.write(chunk.raw_data)
#     stream.stop_stream()
#     stream.close()
#     p.terminate()

def speech(dialogue):
    print("Brad: ", dialogue)
    os.system(f'say -v Alex "{dialogue}"')
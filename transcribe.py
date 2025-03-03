import speech_recognition as sr

# Initialize recognizer
recognizer = sr.Recognizer()

# Create a microphone instance
mic = sr.Microphone()

# Open the output file for writing
with open("transcription.txt", "a") as file:
    print("Listening...")
    
    while True:
        try:
            # Listen for the audio and convert it to text
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)  # Adjust for ambient noise
                audio = recognizer.listen(source)

            # Recognize the speech
            text = recognizer.recognize_google(audio)
            print(f"Recognized: {text}")
            
            # Write the recognized text to the file
            file.write(text + '\n')

        except sr.UnknownValueError:
            print("Could not understand the audio. Trying again...")
        except sr.RequestError as e:
            print(f"Error with the request: {e}")
            break

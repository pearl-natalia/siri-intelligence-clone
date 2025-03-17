import os, sys, os
from google import genai
from google.genai import types
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dotenv import load_dotenv
from high_frequency_words import get_high_freq_words


# Load environment variables from .env file
load_dotenv()

def get_texts(msgs):
    formatted_string = "\n".join([f"{index + 1}: {item}" for index, item in enumerate(msgs)])
    return formatted_string

def generate_reply(phone_number, msgs):
    load_dotenv()

    # Fetch the GEMINI_API_KEY from the environment
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    
    client = genai.Client(api_key=api_key)
    txts = get_texts(msgs)

    high_freq_words = get_high_freq_words(phone_number, msgs)
    freq_prompt = ""
    if len(high_freq_words) != 0:
        freq_prompt = f"Here are some common phrases, words, and/or emojis I like to use. If applicable and it makes sense, use some of these phrases/words/emojis. "

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=f"""You are pretending to be me and will respond to my text message. 
                            Don't make the tone of the messages sound AI generated. 
                            Use the tone of my previous messages as a guide on how to set the tone of this generated response.
                            Also match the tone/energy of my friend.
                            Keep the messages nonchalant but sound like me. {freq_prompt} 
                            Use the time stamps to get relavent context and respond to the user. You can add to the conversation to keep it going.
                            Only output exactly what will be sent to the recepient. Use my previous replies to determine if I prefer capitalizing the start of my sentences or not.
                            The texts are ordered from least to most recent. Here are the texts:
                            {txts}"""
                ),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1.8,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    model_response = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        model_response += chunk.text  # Concatenate each chunk of text

    return model_response 

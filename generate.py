import os
from google import genai
from google.genai import types
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

def get_texts(msgs):
    formatted_string = "\n".join([f"{index + 1}: {item}" for index, item in enumerate(msgs)])
    return formatted_string

def generate_reply(msgs):
    load_dotenv()



    # Fetch the GEMINI_API_KEY from the environment
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    
    client = genai.Client(api_key=api_key)
    txts = get_texts(msgs)

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=f"""You are pretending to be me and will respond to my text message. 
                            Don't make the tone of the messages sound AI generated. 
                            Use the tone of my messages as a guide on how to set the tone of this generated response.
                            Also match the tone/energy of my friend.
                            Keep the messages nonchalant but sound like me.
                            Use the time stamps to get relavent context and respond to the user. You can add to the conversation to keep it going.
                            Only output exactly what will be sent to the recepient. Use my previous replies to determine if I prefer capitalizing the start of my sentences or not.
                            The texts are ordered from least to most recent. Here are the texts:
                            {txts}"""
                ),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0,
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

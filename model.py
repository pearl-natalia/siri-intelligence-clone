import os, sqlite3
from google import genai
from google.genai import types
from dotenv import load_dotenv

conversation_history = []
MAX_HISTORY = 20
# Short term history
def add_user_message(content):
    conversation_history.append({"role": "user", "content": content})
    trim_history()

def add_assistant_message(content):
    conversation_history.append({"role": "assistant", "content": content})
    trim_history()

def trim_history():
    global conversation_history
    conversation_history = conversation_history[-MAX_HISTORY:]

def get_history():
    return conversation_history

def model(prompt, tmp, short_term_history=False):
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    
    client = genai.Client(api_key=api_key)
    model = "gemini-2.0-flash"
    
    contents = []
    
    # History
    if short_term_history:
        for entry in conversation_history:
            contents.append(
                types.Content(
                    role=entry["role"],
                    parts=[types.Part.from_text(text=entry["content"])]
                )
            )

    # Prompt
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text = prompt,
                ),
            ],
        ),
    )
    
    generate_content_config = types.GenerateContentConfig(
        temperature=tmp,
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
        model_response += chunk.text 

    if model_response.startswith("```"):
        model_response = model_response[3:].strip()
    if model_response.endswith("```"):
        model_response = model_response[:-3].strip()
    return model_response.strip()
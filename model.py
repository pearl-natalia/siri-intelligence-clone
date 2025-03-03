import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

def model(prompt, tmp):
    load_dotenv()
    
    # Fetch the GEMINI_API_KEY from the environment
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    
    client = genai.Client(api_key=api_key)
    model = "gemini-2.0-flash"
    
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text = prompt,
                ),
            ],
        ),
    ]
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
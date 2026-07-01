import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

conversation_history = []
MAX_HISTORY = 20
MODEL_ID = "gemini-3.5-flash"


def add_user_message(content):
    conversation_history.append({"role": "user", "content": content})
    _trim_history()

def add_assistant_message(content):
    conversation_history.append({"role": "assistant", "content": content})
    _trim_history()

def _trim_history():
    global conversation_history
    conversation_history = conversation_history[-MAX_HISTORY:]

def get_history():
    return conversation_history


def _client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing from .env")
    return genai.Client(api_key=api_key)


def model(prompt: str, tmp: float, short_term_history: bool = False) -> str:
    """Streaming text call — used by individual action modules."""
    client = _client()
    model_id = MODEL_ID

    contents = []
    if short_term_history:
        for entry in conversation_history:
            contents.append(types.Content(
                role="model" if entry["role"] == "assistant" else entry["role"],
                parts=[types.Part.from_text(text=entry["content"])]
            ))

    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    ))

    config = types.GenerateContentConfig(
        temperature=tmp,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="text/plain",
    )

    response_text = ""
    for chunk in client.models.generate_content_stream(
        model=model_id,
        contents=contents,
        config=config,
    ):
        response_text += chunk.text

    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text[3:].strip()
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()
    return response_text.strip()


def generate(
    contents: list,
    tools: list = None,
    system_instruction: str = None,
    temperature: float = 1.0,
):
    """Non-streaming call for the agent loop (supports function calling)."""
    client = _client()
    config_kwargs = {"temperature": temperature}
    if tools:
        config_kwargs["tools"] = tools
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    return client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )

import sys, json
from transcription.speech import speech
from transcription.transcribe import transcribe
from model import add_user_message, add_assistant_message, get_history
import agent
import memory


def _get_content():
    with open("transcription/transcription.txt", "r") as f:
        content = f.read().strip()
    return content if content else None


def _get_settings() -> dict:
    with open("settings.json", "r") as f:
        return json.load(f)


def decision():
    settings = _get_settings()
    user_name = settings.get("user_first_name", "there")

    content = _get_content()

    if content is None:
        speech(f"What can I do for you, {user_name}?")
        content = _get_content()
        if content is None:
            speech("Sorry, I didn't catch that. Could you repeat yourself?")
            content = _get_content()
            if content is None:
                sys.exit()

    print(f"User: {content}")
    add_user_message(content)

    response = agent.run(content, settings)

    add_assistant_message(response)
    speech(response)


if __name__ == "__main__":
    try:
        while True:
            decision()
    finally:
        memory.save_session(get_history())

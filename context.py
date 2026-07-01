import subprocess, base64, tempfile, os, json, time


def get_clipboard() -> str:
    previous = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to keystroke "c" using command down'],
        capture_output=True,
    )
    time.sleep(0.1)
    selected = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["pbcopy"], input=previous, text=True)
    return selected if selected != previous.strip() else previous.strip()


def get_screenshot_base64() -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    subprocess.run(["screencapture", "-x", path], capture_output=True)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    os.unlink(path)
    return data


def _needs_context(user_input: str) -> dict:
    from model import _client
    from google.genai import types

    client = _client()
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=user_input,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "needs_clipboard": {"type": "boolean"},
                    "needs_screenshot": {"type": "boolean"},
                },
                "required": ["needs_clipboard", "needs_screenshot"],
            },
            system_instruction=(
                "Determine whether answering this voice command requires "
                "reading the user's clipboard or taking a screenshot of their screen. "
                "Return needs_clipboard=true if the user references copied text, 'this', 'that', or selected content. "
                "Return needs_screenshot=true if the user references their screen, what they're looking at, or visible content."
            ),
            temperature=0.0,
        ),
    )
    return json.loads(response.text)


def build_context(user_input: str) -> tuple:
    # Returns (augmented_input, screenshot_base64_or_None)
    try:
        flags = _needs_context(user_input)
    except Exception:
        return user_input, None

    extra = []
    screenshot = None

    if flags.get("needs_clipboard"):
        clipboard = get_clipboard()
        if clipboard:
            extra.append(f"[Clipboard content: {clipboard}]")

    if flags.get("needs_screenshot"):
        screenshot = get_screenshot_base64()
        extra.append("[Screenshot attached]")

    augmented = user_input + "\n" + "\n".join(extra) if extra else user_input
    return augmented, screenshot

import subprocess, json, os, sys, requests
from datetime import datetime
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Tool declarations (passed to Gemini)
# ---------------------------------------------------------------------------

_DECLARATIONS = [
    {
        "name": "get_weather",
        "description": "Get current or forecast weather for a city or the user's current location.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, or 'current' for the user's current location.",
                },
                "forecast_type": {
                    "type": "string",
                    "enum": ["current", "forecast"],
                    "description": "'current' for right now, 'forecast' for a future date.",
                },
            },
            "required": ["city", "forecast_type"],
        },
    },
    {
        "name": "get_time",
        "description": "Get the current time in a specific city or locally.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, or 'current' for the user's local time.",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "control_music",
        "description": (
            "Play music on Spotify or control playback. "
            "Use action='play' with query and music_type to play something. "
            "Use action='pause', 'next', 'previous', 'volume_up', or 'volume_down' for playback control."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "next", "previous", "volume_up", "volume_down"],
                },
                "query": {
                    "type": "string",
                    "description": "Song, album, artist, or playlist name. Required when action is 'play'.",
                },
                "music_type": {
                    "type": "string",
                    "enum": ["track", "album", "artist", "playlist"],
                    "description": "Type of content to play. Required when action is 'play'.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "manage_calendar",
        "description": "View, create, modify, or delete Apple Calendar events.",
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The full calendar request to fulfill.",
                },
            },
            "required": ["request"],
        },
    },
    {
        "name": "execute_system_command",
        "description": (
            "Execute a macOS system action via AppleScript: adjust volume or brightness, "
            "open or close apps, get directions, create notes, change settings, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The system task to perform.",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "send_imessage",
        "description": "Send an iMessage to a contact.",
        "parameters": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Recipient name, phone number, or email.",
                },
                "message": {
                    "type": "string",
                    "description": "The message content to send.",
                },
            },
            "required": ["contact", "message"],
        },
    },
    {
        "name": "send_email",
        "description": "Draft and send an email to a contact via Apple Mail.",
        "parameters": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Recipient name, phone number, or email.",
                },
                "content": {
                    "type": "string",
                    "description": "The user's original email request (full context).",
                },
            },
            "required": ["contact", "content"],
        },
    },
    {
        "name": "start_facetime",
        "description": "Start a FaceTime call with a contact.",
        "parameters": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Name or phone number of the person to FaceTime.",
                },
            },
            "required": ["contact"],
        },
    },
]

TOOLS = [types.Tool(function_declarations=_DECLARATIONS)]


# ---------------------------------------------------------------------------
# Tool executor — maps tool names to Python implementations
# ---------------------------------------------------------------------------

def execute_tool(name: str, args: dict) -> str:
    """Dispatch a tool call and return a string result for Gemini to format."""
    dispatch = {
        "get_weather":          _get_weather,
        "get_time":             _get_time,
        "control_music":        _control_music,
        "manage_calendar":      _manage_calendar,
        "execute_system_command": _execute_system_command,
        "send_imessage":        _send_imessage,
        "send_email":           _send_email,
        "start_facetime":       _start_facetime,
    }
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**args)
    except Exception as e:
        return f"Tool '{name}' encountered an error: {e}"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _get_weather(city: str, forecast_type: str) -> str:
    api_key = os.getenv("WEATHER_API")
    if not api_key:
        return "Weather API key not configured."

    if city.lower() == "current":
        from system.system import get_location
        from geopy.geocoders import Nominatim
        coords = get_location()
        if not coords:
            return "Could not determine current location."
        loc = Nominatim(user_agent="swift_assistant").reverse(coords, language="en")
        city = loc.raw["address"].get("city", "Unknown") if loc else "Unknown"

    url = f"https://api.weatherapi.com/v1/{forecast_type}.json?key={api_key}&q={city}"
    try:
        data = requests.get(url, timeout=5).json()
        if forecast_type == "current":
            c = data.get("current", {})
            l = data.get("location", {})
            return (
                f"{l.get('name', city)}, {l.get('country', '')}: "
                f"{c.get('temp_c')}°C / {c.get('temp_f')}°F, "
                f"{c.get('condition', {}).get('text', '')}, "
                f"feels like {c.get('feelslike_c')}°C, "
                f"humidity {c.get('humidity')}%"
            )
        days = data.get("forecast", {}).get("forecastday", [])
        lines = [
            f"{d['date']}: avg {d['day']['avgtemp_c']}°C, {d['day']['condition']['text']}"
            for d in days[:3]
        ]
        return "3-day forecast:\n" + "\n".join(lines)
    except Exception as e:
        return f"Weather lookup failed: {e}"


def _get_time(city: str) -> str:
    if city.lower() == "current":
        return datetime.now().strftime("%I:%M %p on %A, %B %d, %Y")
    from model import model
    script = model(
        f'Generate an osascript to get the current date and time in {city}. '
        'Only output the AppleScript string, nothing else. '
        'Example for Dubai: return do shell script "TZ=Asia/Dubai date"',
        1.0
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else f"Could not get time for {city}."


def _control_music(action: str, query: str = None, music_type: str = None) -> str:
    if action == "play":
        if not query:
            return "No song or artist specified."
        if not music_type:
            music_type = "track"
        from system.music import get_spotify_id
        spotify_id = get_spotify_id(query, music_type)
        if spotify_id:
            script = f'tell application "Spotify" to play {music_type} "spotify:{music_type}:{spotify_id}"'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return f"Playing {query} on Spotify." if r.returncode == 0 else "Failed to play on Spotify."
        return f"Could not find '{query}' on Spotify."

    scripts = {
        "pause":       'tell application "Spotify" to pause',
        "next":        'tell application "Spotify" to next track',
        "previous":    'tell application "Spotify" to previous track',
        "volume_up":   'set volume output volume ((output volume of (get volume settings)) + 20)',
        "volume_down": 'set volume output volume ((output volume of (get volume settings)) - 20)',
    }
    script = scripts.get(action)
    if not script:
        return f"Unknown music action: {action}"
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return "Done." if r.returncode == 0 else f"Failed: {r.stderr.strip()}"


def _manage_calendar(request: str) -> str:
    from system.auto_calendar import calendar
    return calendar(request)


def _execute_system_command(task: str) -> str:
    from system.system import adjust_system
    return adjust_system(task)


def _send_imessage(contact: str, message: str) -> str:
    from communication.find_contact import find_similar_contact, get_phone_number

    match = find_similar_contact(contact)
    if match.strip() == "No match":
        return f"Could not find contact: {contact}."

    parts = [p.strip() for p in match.split(",", 1)]
    first = parts[0]
    last = parts[1].strip('"') if len(parts) > 1 else ""

    phone = get_phone_number(first, last)
    if not phone:
        return f"No phone number found for {contact}."
    phone = phone.splitlines()[0].strip()

    safe_msg = message.replace('"', '\\"')
    script = f'''tell application "Messages"
    set targetService to 1st service whose service type is iMessage
    set targetBuddy to buddy "{phone}" of targetService
    send "{safe_msg}" to targetBuddy
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return f"Message sent to {first}." if r.returncode == 0 else f"Failed to send message: {r.stderr.strip()}"


def _send_email(contact: str, content: str) -> str:
    from communication.auto_email.generate_email import generate_email
    generate_email(content)
    return f"Email drafted to {contact} in Apple Mail."


def _start_facetime(contact: str) -> str:
    from communication.auto_facetime.facetime import facetime
    facetime(contact)
    return f"Starting FaceTime with {contact}."

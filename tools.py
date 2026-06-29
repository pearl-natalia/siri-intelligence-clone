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
            "open or close apps, get directions, create notes, change settings, "
            "Safari/browser control (open tabs, search, bookmark), and anything else "
            "that can be automated on macOS."
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
        "name": "finder",
        "description": "Control Finder: open folders, find files, move or rename files, reveal items in Finder.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The Finder task to perform, e.g. 'open downloads folder', 'find my resume'.",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "manage_contacts",
        "description": "Look up, add, or update contacts in the Apple Contacts app.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["lookup", "add", "update"],
                    "description": "'lookup' to get contact info, 'add' to create a new contact, 'update' to change existing info.",
                },
                "name": {
                    "type": "string",
                    "description": "The contact's name.",
                },
                "field": {
                    "type": "string",
                    "description": "What to look up or update: 'phone', 'email', 'address'.",
                },
                "value": {
                    "type": "string",
                    "description": "The value to set when adding or updating.",
                },
            },
            "required": ["action", "name"],
        },
    },
    {
        "name": "create_reminder",
        "description": "Create a reminder in the Apple Reminders app.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What to be reminded about.",
                },
                "time": {
                    "type": "string",
                    "description": "When to trigger the reminder, e.g. 'today at 6pm', 'tomorrow at 9am'.",
                },
            },
            "required": ["task"],
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

def execute_tool(name: str, args: dict) -> dict:
    # Returns {"success": bool, "message": str}
    dispatch = {
        "get_weather":            _get_weather,
        "get_time":               _get_time,
        "control_music":          _control_music,
        "manage_calendar":        _manage_calendar,
        "execute_system_command": _execute_system_command,
        "send_imessage":          _send_imessage,
        "send_email":             _send_email,
        "create_reminder":        _create_reminder,
        "finder":                 _finder,
        "manage_contacts":        _manage_contacts,
        "start_facetime":         _start_facetime,
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"success": False, "message": f"Unknown tool: {name}"}
    try:
        return fn(**args)
    except Exception as e:
        return {"success": False, "message": f"Tool '{name}' failed: {e}"}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _ok(message: str) -> dict:
    return {"success": True, "message": message}

def _err(message: str) -> dict:
    return {"success": False, "message": message}


def _get_weather(city: str, forecast_type: str) -> dict:
    api_key = os.getenv("WEATHER_API")
    if not api_key:
        return _err("Weather API key not configured.")

    if city.lower() == "current":
        from system.system import get_location
        from geopy.geocoders import Nominatim
        coords = get_location()
        if not coords:
            return _err("Could not determine current location.")
        loc = Nominatim(user_agent="swift_assistant").reverse(coords, language="en")
        city = loc.raw["address"].get("city", "Unknown") if loc else "Unknown"

    url = f"https://api.weatherapi.com/v1/{forecast_type}.json?key={api_key}&q={city}"
    try:
        data = requests.get(url, timeout=5).json()
        if "error" in data:
            return _err(data["error"].get("message", "Weather API error."))
        if forecast_type == "current":
            c = data.get("current", {})
            l = data.get("location", {})
            return _ok(
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
        return _ok("3-day forecast:\n" + "\n".join(lines))
    except Exception as e:
        return _err(f"Weather lookup failed: {e}")


def _get_time(city: str) -> dict:
    if city.lower() == "current":
        return _ok(datetime.now().strftime("%I:%M %p on %A, %B %d, %Y"))
    from react import applescript_loop
    return applescript_loop(
        f"Get the current date and time in {city} and return it as a string.",
        system_context='Example for Dubai: return do shell script "TZ=Asia/Dubai date"'
    )


def _control_music(action: str, query: str = None, music_type: str = None) -> dict:
    if action == "play":
        if not query:
            return _err("No song or artist specified.")
        if not music_type:
            music_type = "track"
        from system.music import get_spotify_id
        spotify_id = get_spotify_id(query, music_type)
        if spotify_id:
            script = f'tell application "Spotify" to play {music_type} "spotify:{music_type}:{spotify_id}"'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return _ok(f"Playing {query} on Spotify.") if r.returncode == 0 else _err(f"Spotify AppleScript failed: {r.stderr.strip()}")
        return _err(f"Could not find '{query}' on Spotify.")

    scripts = {
        "pause":       'tell application "Spotify" to pause',
        "next":        'tell application "Spotify" to next track',
        "previous":    'tell application "Spotify" to previous track',
        "volume_up":   'set volume output volume ((output volume of (get volume settings)) + 20)',
        "volume_down": 'set volume output volume ((output volume of (get volume settings)) - 20)',
    }
    script = scripts.get(action)
    if not script:
        return _err(f"Unknown music action: {action}")
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return _ok("Done.") if r.returncode == 0 else _err(r.stderr.strip())


def _manage_calendar(request: str) -> dict:
    from system.auto_calendar import calendar
    result = calendar(request)
    return _ok(result)


def _execute_system_command(task: str) -> dict:
    from react import applescript_loop
    from system.system import get_location
    from datetime import datetime
    context = (
        f"Today is {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}. "
        f"Current location: {get_location()}. "
        f"User settings: {json.load(open('settings.json'))}"
    )
    return applescript_loop(task, system_context=context)


def _send_imessage(contact: str, message: str) -> dict:
    from communication.find_contact import find_similar_contact, get_phone_number

    match = find_similar_contact(contact)
    if match.strip() == "No match":
        return _err(f"Could not find contact: {contact}.")

    parts = [p.strip() for p in match.split(",", 1)]
    first = parts[0]
    last = parts[1].strip('"') if len(parts) > 1 else ""

    phone = get_phone_number(first, last)
    if not phone:
        return _err(f"No phone number found for {contact}.")
    phone = phone.splitlines()[0].strip()

    safe_msg = message.replace('"', '\\"')
    script = f'''tell application "Messages"
    set targetService to 1st service whose service type is iMessage
    set targetBuddy to buddy "{phone}" of targetService
    send "{safe_msg}" to targetBuddy
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return _ok(f"Message sent to {first}.") if r.returncode == 0 else _err(f"iMessage failed: {r.stderr.strip()}")


def _send_email(contact: str, content: str) -> dict:
    from communication.auto_email.generate_email import generate_email
    generate_email(content)
    return _ok(f"Email drafted to {contact} in Apple Mail.")


def _create_reminder(task: str, time: str = None) -> dict:
    if time:
        from model import model
        script = model(
            f'Generate an AppleScript to create a reminder in the Reminders app with the name "{task}" '
            f'due at "{time}". Today is {datetime.now().strftime("%A, %B %d, %Y %I:%M %p")}. '
            'Only output the AppleScript, nothing else.',
            1.0
        )
    else:
        script = f'''tell application "Reminders"
    set newReminder to make new reminder with properties {{name:"{task}"}}
end tell'''

    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode == 0:
        msg = f"Reminder set: '{task}'" + (f" at {time}." if time else ".")
        return _ok(msg)
    return _err(f"Failed to create reminder: {r.stderr.strip()}")


def _finder(task: str) -> dict:
    from react import applescript_loop
    return applescript_loop(task, system_context="You are controlling Finder on macOS.")


def _manage_contacts(action: str, name: str, field: str = None, value: str = None) -> dict:
    from communication.find_contact import find_similar_contact, get_phone_number, name_to_email

    if action == "lookup":
        match = find_similar_contact(name)
        if match.strip() == "No match":
            return _err(f"No contact found for '{name}'.")
        parts = [p.strip() for p in match.split(",", 1)]
        first = parts[0]
        last = parts[1].strip('"') if len(parts) > 1 else ""
        if not field or field == "phone":
            phone = get_phone_number(first, last)
            return _ok(f"{first} {last}: {phone}") if phone else _err(f"No phone number for {name}.")
        if field == "email":
            email = name_to_email(first, last)
            return _ok(f"{first} {last}: {email}") if email else _err(f"No email for {name}.")
        return _err(f"Unknown field: {field}")

    if action == "add":
        if not value:
            return _err("A value is required to add a contact.")
        script = f'''tell application "Contacts"
    set newPerson to make new person with properties {{first name:"{name}"}}
    make new phone at end of phones of newPerson with properties {{value:"{value}", label:"mobile"}}
    save
end tell'''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return _ok(f"Contact '{name}' added.") if r.returncode == 0 else _err(r.stderr.strip())

    if action == "update":
        if not value or not field:
            return _err("Both field and value are required to update a contact.")
        from react import applescript_loop
        return applescript_loop(
            f"Update the {field} of contact '{name}' to '{value}' in the Contacts app."
        )

    return _err(f"Unknown action: {action}")


def _start_facetime(contact: str) -> dict:
    from communication.auto_facetime.facetime import facetime
    facetime(contact)
    return _ok(f"Starting FaceTime with {contact}.")

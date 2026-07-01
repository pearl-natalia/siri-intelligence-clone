import subprocess, json, os, sys, requests, re, html, time
from datetime import datetime, date
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Tool declarations (passed to Gemini)
# ---------------------------------------------------------------------------

_DECLARATIONS = [
    {
        "name": "ask_clarification",
        "description": (
            "Ask the user a short follow-up question when the request is ambiguous, "
            "missing required information, or has multiple plausible interpretations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The concise clarification question to ask the user.",
                },
                "reason": {
                    "type": "string",
                    "description": "What information is missing or ambiguous.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current, daily forecast, or hourly weather for a city or the user's current location. Use this for all weather, rain, temperature, forecast, and outdoor timing questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, or 'current' for the user's current location.",
                },
                "forecast_type": {
                    "type": "string",
                    "enum": ["current", "forecast", "hourly"],
                    "description": "'current' for right now, 'forecast' for daily + useful hourly windows, 'hourly' for hourly conditions.",
                },
                "date": {
                    "type": "string",
                    "description": "Optional day for forecast or hourly weather, e.g. 'today', 'tomorrow', or '2026-07-01'.",
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
        "name": "web_search",
        "description": (
            "Search the web for current facts, recent events, sports scores, news, "
            "recipes, articles, pages, or anything that may have changed since the model was trained. "
            "Returns source URLs; include the best URL in the final answer unless another tool opens it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The precise web search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many search snippets to return. Use 3 unless more are needed.",
                },
                "open_first_result": {
                    "type": "boolean",
                    "description": "Open the best search result in the browser. Use true for requests like finding/opening a recipe, article, page, or source the user will likely want to view.",
                },
            },
            "required": ["query"],
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
                    "description": "Song, album, artist, playlist, genre, or mood. Preserve the user's wording when possible, e.g. 'good background music' should stay background music, not be rewritten as study music.",
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
        "name": "manage_reminders",
        "description": "List, create, update, complete, or delete reminders in Apple Reminders.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "update", "complete", "delete"],
                    "description": "The reminder action to perform.",
                },
                "task": {
                    "type": "string",
                    "description": "Reminder title or search text.",
                },
                "new_task": {
                    "type": "string",
                    "description": "New title when updating a reminder.",
                },
                "time": {
                    "type": "string",
                    "description": "Due time for create or update, e.g. 'today at 6pm'.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "manage_notes",
        "description": "Create, search, read, append to, or delete Apple Notes notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "search", "read", "append", "delete"],
                    "description": "The Notes action to perform.",
                },
                "title": {
                    "type": "string",
                    "description": "Note title or search text.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to create or append.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "browser",
        "description": "Control Safari: open URLs, search the web, get the current page, bookmark, or open a new tab.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open_url", "search_web", "get_current_page", "bookmark_current_page", "new_tab"],
                    "description": "The Safari browser action to perform.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for search_web.",
                },
                "url": {
                    "type": "string",
                    "description": "URL for open_url or new_tab.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "maps",
        "description": "Open Apple Maps searches or directions.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "directions"],
                    "description": "Search for a place or open directions.",
                },
                "destination": {
                    "type": "string",
                    "description": "Place or destination address.",
                },
                "origin": {
                    "type": "string",
                    "description": "Optional starting address for directions.",
                },
                "travel_mode": {
                    "type": "string",
                    "enum": ["driving", "walking", "transit"],
                    "description": "Directions mode.",
                },
            },
            "required": ["action", "destination"],
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
        "ask_clarification":      _ask_clarification,
        "get_weather":            _get_weather,
        "get_time":               _get_time,
        "web_search":             _web_search,
        "control_music":          _control_music,
        "manage_calendar":        _manage_calendar,
        "execute_system_command": _execute_system_command,
        "send_imessage":          _send_imessage,
        "send_email":             _send_email,
        "create_reminder":        _create_reminder,
        "manage_reminders":       _manage_reminders,
        "manage_notes":           _manage_notes,
        "browser":                _browser,
        "maps":                   _maps,
        "finder":                 _finder,
        "manage_contacts":        _manage_contacts,
        "start_facetime":         _start_facetime,
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"success": False, "message": f"Unknown tool: {name}"}
    try:
        public_args = {k: v for k, v in args.items() if not k.startswith("_")}
        return fn(**public_args)
    except Exception as e:
        return {"success": False, "message": f"Tool '{name}' failed: {e}"}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _ok(message: str) -> dict:
    return {"success": True, "message": message}

def _err(message: str) -> dict:
    return {"success": False, "message": message}


def _as_string(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def _open_url(url: str) -> dict:
    r = subprocess.run(["open", url], capture_output=True, text=True)
    return _ok("Opened.") if r.returncode == 0 else _err(r.stderr.strip())


def _ask_clarification(question: str, reason: str = None) -> dict:
    return {"success": False, "message": question}


def _hour_label(hour: dict) -> str:
    dt = datetime.strptime(hour["time"], "%Y-%m-%d %H:%M")
    return dt.strftime("%-I %p")


def _hour_score(hour: dict) -> float:
    temp_c = float(hour.get("temp_c", 20))
    rain = float(hour.get("chance_of_rain", 0))
    wind = float(hour.get("wind_kph", 0))
    temp_penalty = abs(temp_c - 22) * 2.0
    return 100 - rain - wind - temp_penalty


def _best_hourly_windows(day: dict) -> str:
    usable = []
    for hour in day.get("hour", []):
        dt = datetime.strptime(hour["time"], "%Y-%m-%d %H:%M")
        if 7 <= dt.hour <= 21:
            usable.append(hour)
    best = sorted(usable, key=_hour_score, reverse=True)[:4]
    best = sorted(best, key=lambda h: h["time"])
    parts = []
    for hour in best:
        parts.append(
            f"{_hour_label(hour)}: {hour.get('temp_c')}°C, "
            f"{hour.get('condition', {}).get('text', '')}, "
            f"rain {hour.get('chance_of_rain', 0)}%, wind {hour.get('wind_kph', 0)} kph"
        )
    return "; ".join(parts)


def _pick_forecast_days(days: list, date: str = None) -> list:
    if not date:
        return days[:2]
    normalized = date.strip().lower()
    if normalized == "today":
        return days[:1]
    if normalized == "tomorrow":
        return days[1:2] if len(days) > 1 else days[:1]
    matches = [day for day in days if day.get("date") == date]
    return matches or days[:2]


def _get_weather(city: str, forecast_type: str, date: str = None) -> dict:
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

    endpoint = "current" if forecast_type == "current" else "forecast"
    url = f"https://api.weatherapi.com/v1/{endpoint}.json?key={api_key}&q={city}"
    if endpoint == "forecast":
        url += "&days=3&aqi=no&alerts=no"
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
        days = _pick_forecast_days(data.get("forecast", {}).get("forecastday", []), date)
        lines = []
        for day in days:
            day_info = day.get("day", {})
            lines.append(
                f"{day['date']}: avg {day_info.get('avgtemp_c')}°C, "
                f"high {day_info.get('maxtemp_c')}°C, low {day_info.get('mintemp_c')}°C, "
                f"{day_info.get('condition', {}).get('text', '')}, "
                f"rain chance {day_info.get('daily_chance_of_rain', 0)}%."
            )
            hourly = _best_hourly_windows(day)
            if hourly:
                lines.append(f"Best hourly outdoor windows for {day['date']}: {hourly}.")
        label = "Hourly forecast" if forecast_type == "hourly" else "Forecast"
        return _ok(f"{label} for {city}:\n" + "\n".join(lines))
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


def _clean_html(text: str) -> str:
    text = re.sub(r"<.*?>", "", text)
    return html.unescape(text).strip()


def _search_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else url
    return url


def _web_search(query: str, max_results: int = 3, open_first_result: bool = False) -> dict:
    if not query:
        return _err("A search query is required.")

    max_results = max(1, min(int(max_results or 3), 5))
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception as e:
        return _err(f"Web search failed: {e}")

    html_text = response.text
    matches = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        flags=re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html_text,
        flags=re.DOTALL,
    )

    results = []
    best_url = None
    best_title = None
    for i, (result_url, title) in enumerate(matches[:max_results]):
        clean_url = _search_url(html.unescape(result_url))
        clean_title = _clean_html(title)
        if i == 0:
            best_url = clean_url
            best_title = clean_title
        snippet = _clean_html(snippets[i]) if i < len(snippets) else ""
        results.append(
            f"{i + 1}. {clean_title}\n"
            f"   {snippet}\n"
            f"   Source: {clean_url}"
        )

    if not results:
        return _err(f"No web results found for '{query}'.")

    if open_first_result and best_url:
        opened = _open_url(best_url)
        if opened["success"]:
            return _ok(f"Opened {best_title}.")
        return _err(f"Found {best_title}, but could not open it: {opened['message']}")

    return _ok("Web results:\n" + "\n".join(results))


def _control_music(action: str, query: str = None, music_type: str = None) -> dict:
    if action == "play":
        if not query:
            return _err("No song or artist specified.")
        if not music_type:
            music_type = "track"
        from system.music import get_spotify_id
        spotify_id = get_spotify_id(query, music_type)
        # Spotify's client-credentials search can't return playlists/albums reliably,
        # so fall back to a track search to still play something relevant.
        if not spotify_id and music_type != "track":
            music_type = "track"
            spotify_id = get_spotify_id(query, music_type)
        if spotify_id:
            uri = f"spotify:{music_type}:{spotify_id}"
            if music_type == "track":
                script = f'tell application "Spotify" to play track "{uri}"'
                r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            else:
                r = subprocess.run(["open", uri], capture_output=True, text=True)
                if r.returncode == 0:
                    time.sleep(1)
                    r = subprocess.run(
                        ["osascript", "-e", 'tell application "Spotify" to activate', "-e", 'tell application "Spotify" to play'],
                        capture_output=True,
                        text=True,
                    )
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


def _clean_calendar_title(title: str) -> str:
    title = re.sub(r"[.?!,;:]+$", "", str(title or "")).strip()
    return re.sub(r"^(my|the|a|an)\s+", "", title, flags=re.IGNORECASE).strip()


def _looks_like_event_title(title: str) -> bool:
    title = _clean_calendar_title(title)
    if not title:
        return False
    lower = title.lower()
    if re.fullmatch(r"(today|tomorrow|tonight|this morning|this afternoon|this evening)", lower):
        return False
    if re.search(r"^(i|we|you|they)\b", lower):
        return False
    if re.search(r"^(have|had|got|scheduled|planned|booked|set)\b", lower):
        return False
    if re.search(r"^(on|for|at|in|to|from|with)\b", lower):
        return False
    return True


def _extract_calendar_title(text: str) -> str:
    quoted = re.search(r"""["']([^"']+)["']""", text)
    if quoted:
        title = _clean_calendar_title(quoted.group(1))
        return title if _looks_like_event_title(title) else ""

    date_boundary = (
        r"(?:\s+(?:today|tomorrow)\b.*|"
        r"\s+(?:on\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?\b.*|$)"
    )
    explicit = re.search(
        r"\b(?:event|meeting|appointment)\s+(?:called|named|about|for|with)\s+(.+?)" + date_boundary,
        text,
        flags=re.IGNORECASE,
    )
    if explicit:
        title = _clean_calendar_title(explicit.group(1))
        return title if _looks_like_event_title(title) else ""

    bare = re.search(
        r"\b(?:event|meeting|appointment)\s+(.+?)" + date_boundary,
        text,
        flags=re.IGNORECASE,
    )
    if bare:
        title = _clean_calendar_title(bare.group(1))
        return title if _looks_like_event_title(title) else ""

    return ""


def _calendar_cancel_details(request: str) -> tuple:
    text = request.strip()
    lower = text.lower()
    if not any(word in lower for word in ("cancel", "delete", "remove")):
        return None, None
    if not any(word in lower for word in ("event", "meeting", "appointment")):
        return None, None

    date_offset, _ = _calendar_date_offset(lower)
    if date_offset is None:
        return None, None

    title = _extract_calendar_title(text)
    return (title or None), date_offset


def _calendar_date_offset(request: str):
    lower = str(request or "").lower()
    today = datetime.now().date()

    if "tomorrow" in lower:
        return 1, "tomorrow"
    if "today" in lower:
        return 0, "today"

    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        lower,
    )
    if not month_match:
        return None, None

    month_names = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    month = month_names[month_match.group(1).rstrip(".")]
    day = int(month_match.group(2))
    target = date(today.year, month, day)
    if target < today:
        target = date(today.year + 1, month, day)
    return (target - today).days, target.strftime("%B %-d")


def _looks_like_calendar_read(request: str) -> bool:
    lower = str(request or "").lower()
    if any(word in lower for word in ("delete", "remove", "cancel", "create", "add", "schedule", "reschedule", "move", "update")):
        return False
    if not any(word in lower for word in ("event", "events", "meeting", "meetings", "calendar", "schedule")):
        return False
    offset, _ = _calendar_date_offset(lower)
    return offset is not None


def _list_calendar_events(request: str) -> dict:
    if not _looks_like_calendar_read(request):
        return None

    date_offset, label = _calendar_date_offset(request)
    script = f'''tell application "Calendar"
    set targetStart to current date
    set time of targetStart to 0
    set targetStart to targetStart + ({date_offset} * days)
    set targetEnd to targetStart + (1 * days)
    set eventNames to {{}}
    repeat with cal in calendars
        set calEvents to (every event of cal whose start date is greater than or equal to targetStart and start date is less than targetEnd)
        repeat with ev in calEvents
            set eventSummary to summary of ev as text
            set eventStart to start date of ev
            set end of eventNames to (eventSummary & " at " & (time string of eventStart))
        end repeat
    end repeat

    if (count of eventNames) is 0 then
        return "You do not have any Calendar events for {label}."
    end if

    set AppleScript's text item delimiters to "; "
    return "Calendar events for {label}: " & (eventNames as text)
end tell'''
    r = _run_applescript(script)
    if r.returncode != 0:
        return _err(f"Calendar lookup failed: {r.stderr.strip()}")
    return _ok(r.stdout.strip() or f"You do not have any Calendar events for {label}.")


def _cancel_calendar_event(request: str) -> dict:
    title, date_offset = _calendar_cancel_details(request)
    if date_offset is None:
        return None

    _, day_name = _calendar_date_offset(request)
    if not title:
        script = f'''tell application "Calendar"
    set targetStart to current date
    set time of targetStart to 0
    set targetStart to targetStart + ({date_offset} * days)
    set targetEnd to targetStart + (1 * days)
    set eventMatches to {{}}
    repeat with cal in calendars
        set calEvents to (every event of cal whose start date is greater than or equal to targetStart and start date is less than targetEnd)
        repeat with ev in calEvents
            set end of eventMatches to ev
        end repeat
    end repeat

    set matchCount to count of eventMatches
    if matchCount is 0 then
        return "No Calendar events were found for {day_name}."
    else if matchCount is greater than 1 then
        set eventNames to {{}}
        repeat with ev in eventMatches
            set end of eventNames to (summary of ev & " at " & ((start date of ev) as string))
        end repeat
        set AppleScript's text item delimiters to "; "
        return "I found multiple Calendar events for {day_name}: " & (eventNames as text)
    end if

    set deletedName to summary of item 1 of eventMatches
    delete item 1 of eventMatches
    delay 0.5
    return "Deleted the " & deletedName & " event for {day_name}."
end tell'''
        r = _run_applescript(script)
        if r.returncode != 0:
            return _err(f"Calendar deletion failed: {r.stderr.strip()}")
        message = r.stdout.strip()
        if message.startswith("Deleted "):
            return _ok(message)
        return _err(message or "Calendar deletion did not complete.")

    safe_title = _as_string(title)
    script = f'''tell application "Calendar"
    set targetStart to current date
    set time of targetStart to 0
    set targetStart to targetStart + ({date_offset} * days)
    set targetEnd to targetStart + (1 * days)
    set eventMatches to {{}}
    repeat with cal in calendars
        set calEvents to (every event of cal whose start date is greater than or equal to targetStart and start date is less than targetEnd)
        repeat with ev in calEvents
            set eventName to summary of ev as text
            ignoring case
                if eventName contains "{safe_title}" then
                    set end of eventMatches to ev
                end if
            end ignoring
        end repeat
    end repeat

    set matchCount to count of eventMatches
    if matchCount is 0 then
        return "No matching event named {safe_title} was found for {day_name}."
    else if matchCount is greater than 1 then
        set eventNames to {{}}
        repeat with ev in eventMatches
            set end of eventNames to (summary of ev & " at " & ((start date of ev) as string))
        end repeat
        set AppleScript's text item delimiters to "; "
        return "Multiple matching events found: " & (eventNames as text)
    end if

    delete item 1 of eventMatches
    delay 0.5

    set remainingMatches to {{}}
    repeat with cal in calendars
        set calEvents to (every event of cal whose start date is greater than or equal to targetStart and start date is less than targetEnd)
        repeat with ev in calEvents
            set eventName to summary of ev as text
            ignoring case
                if eventName contains "{safe_title}" then
                    set end of remainingMatches to ev
                end if
            end ignoring
        end repeat
    end repeat

    if (count of remainingMatches) is 0 then
        return "Deleted the {safe_title} event for {day_name}."
    else
        return "I tried to delete {safe_title}, but it still appears on the calendar."
    end if
end tell'''
    r = _run_applescript(script)
    if r.returncode != 0:
        return _err(f"Calendar deletion failed: {r.stderr.strip()}")
    message = r.stdout.strip()
    if message.startswith("Deleted "):
        return _ok(message)
    return _err(message or "Calendar deletion did not complete.")


def _manage_calendar(request: str) -> dict:
    direct_list = _list_calendar_events(request)
    if direct_list is not None:
        return direct_list

    direct_cancel = _cancel_calendar_event(request)
    if direct_cancel is not None:
        return direct_cancel

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
    import clarification
    from communication.find_contact import get_contact_list, find_similar_contact, get_phone_number

    candidates = clarification.contact_candidates(contact, get_contact_list())
    if clarification.needs_contact_clarification(contact, candidates):
        return clarification.ask_contact(
            "send_imessage",
            {"contact": contact, "message": message},
            "contact",
            candidates,
        )

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


def _manage_reminders(action: str, task: str = None, new_task: str = None, time: str = None) -> dict:
    if action == "create":
        if not task:
            return _err("A reminder title is required.")
        return _create_reminder(task, time)

    if action == "list":
        script = '''tell application "Reminders"
    set output to {}
    repeat with r in reminders whose completed is false
        set end of output to name of r
    end repeat
    return output as text
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip() or "No incomplete reminders found.") if r.returncode == 0 else _err(r.stderr.strip())

    if not task:
        return _err("A reminder title or search text is required.")

    from react import applescript_loop
    if action == "update":
        if not new_task and not time:
            return _err("Tell me what to change about the reminder.")
        changes = []
        if new_task:
            changes.append(f'title to "{new_task}"')
        if time:
            changes.append(f'due date to "{time}"')
        return applescript_loop(
            f'Find the incomplete reminder matching "{task}" and update its {", ".join(changes)}. '
            "If there are multiple matches, return a clear ambiguity error instead of changing anything.",
            system_context=f"Today is {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}.",
        )

    if action == "complete":
        return applescript_loop(
            f'Find the incomplete reminder matching "{task}" and mark it complete. '
            "If there are multiple matches, return a clear ambiguity error instead of changing anything.",
        )

    if action == "delete":
        return applescript_loop(
            f'Find the reminder matching "{task}" and delete it. '
            "If there are multiple matches, return a clear ambiguity error instead of deleting anything.",
        )

    return _err(f"Unknown reminder action: {action}")


def _manage_notes(action: str, title: str = None, content: str = None) -> dict:
    safe_title = _as_string(title)
    safe_content = _as_string(content)

    if action == "create":
        if not title and not content:
            return _err("A title or content is required to create a note.")
        note_title = safe_title or "Untitled"
        body = safe_content or note_title
        script = f'''tell application "Notes"
    tell default account
        make new note at default folder with properties {{name:"{note_title}", body:"{body}"}}
    end tell
end tell'''
        r = _run_applescript(script)
        return _ok(f"Created note '{note_title}'.") if r.returncode == 0 else _err(r.stderr.strip())

    if action == "search":
        if not title:
            return _err("Search text is required.")
        script = f'''tell application "Notes"
    set matches to {{}}
    repeat with n in notes
        if name of n contains "{safe_title}" or body of n contains "{safe_title}" then
            set end of matches to name of n
        end if
    end repeat
    return matches as text
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip() or "No matching notes found.") if r.returncode == 0 else _err(r.stderr.strip())

    if action == "read":
        if not title:
            return _err("A note title or search text is required.")
        script = f'''tell application "Notes"
    repeat with n in notes
        if name of n contains "{safe_title}" then
            return name of n & linefeed & body of n
        end if
    end repeat
    return "No matching note found."
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip()) if r.returncode == 0 else _err(r.stderr.strip())

    if action == "append":
        if not title or not content:
            return _err("A title and content are required to append to a note.")
        script = f'''tell application "Notes"
    repeat with n in notes
        if name of n contains "{safe_title}" then
            set body of n to (body of n) & "<br>" & "{safe_content}"
            return "Updated note " & name of n
        end if
    end repeat
    return "No matching note found."
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip()) if r.returncode == 0 else _err(r.stderr.strip())

    if action == "delete":
        if not title:
            return _err("A note title or search text is required.")
        script = f'''tell application "Notes"
    repeat with n in notes
        if name of n contains "{safe_title}" then
            set noteName to name of n
            delete n
            return "Deleted note " & noteName
        end if
    end repeat
    return "No matching note found."
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip()) if r.returncode == 0 else _err(r.stderr.strip())

    return _err(f"Unknown Notes action: {action}")


def _browser(action: str, query: str = None, url: str = None) -> dict:
    if action == "search_web":
        if not query:
            return _err("A search query is required.")
        from urllib.parse import quote_plus
        return _open_url(f"https://www.google.com/search?q={quote_plus(query)}")

    if action in {"open_url", "new_tab"}:
        if not url:
            return _err("A URL is required.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        safe_url = _as_string(url)
        script = f'''tell application "Safari"
    activate
    if (count of windows) is 0 then make new document
    tell front window to make new tab with properties {{URL:"{safe_url}"}}
end tell'''
        r = _run_applescript(script)
        return _ok(f"Opened {url} in Safari.") if r.returncode == 0 else _err(r.stderr.strip())

    if action == "get_current_page":
        script = '''tell application "Safari"
    if (count of windows) is 0 then return "Safari has no open windows."
    return name of current tab of front window & " — " & URL of current tab of front window
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip()) if r.returncode == 0 else _err(r.stderr.strip())

    if action == "bookmark_current_page":
        script = '''tell application "Safari"
    if (count of windows) is 0 then return "Safari has no open windows."
    set pageName to name of current tab of front window
    set pageUrl to URL of current tab of front window
    add reading list item pageUrl with title pageName
    return "Added " & pageName & " to Reading List."
end tell'''
        r = _run_applescript(script)
        return _ok(r.stdout.strip()) if r.returncode == 0 else _err(r.stderr.strip())

    return _err(f"Unknown browser action: {action}")


def _maps(action: str, destination: str, origin: str = None, travel_mode: str = "driving") -> dict:
    from urllib.parse import quote_plus
    if not destination:
        return _err("A destination is required.")

    if action == "search":
        return _open_url(f"maps://?q={quote_plus(destination)}")

    if action == "directions":
        mode = {"driving": "d", "walking": "w", "transit": "r"}.get(travel_mode or "driving", "d")
        url = f"maps://?daddr={quote_plus(destination)}&dirflg={mode}"
        if origin:
            url += f"&saddr={quote_plus(origin)}"
        return _open_url(url)

    return _err(f"Unknown Maps action: {action}")


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

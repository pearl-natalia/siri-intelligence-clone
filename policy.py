import re
from urllib.parse import urlparse


_PENDING_ACTION = None
ALLOW = "allow"
CONFIRM = "confirm"
BLOCK = "block"
CLARIFY = "clarify"

# Policy is intentionally deterministic. The model can propose an action, but this
# table is the source of truth for whether Python will execute it.
_TOOL_POLICIES = {
    "ask_clarification": ALLOW,
    "get_weather": ALLOW,
    "get_time": ALLOW,
    "web_search": ALLOW,
    "create_reminder": ALLOW,
    "send_imessage": CONFIRM,
    "send_email": CONFIRM,
    "start_facetime": CONFIRM,
}

_ACTION_POLICIES = {
    "control_music": {
        "play": ALLOW,
        "pause": ALLOW,
        "next": ALLOW,
        "previous": ALLOW,
        "volume_up": ALLOW,
        "volume_down": ALLOW,
    },
    "manage_reminders": {
        "list": ALLOW,
        "create": ALLOW,
        "update": CONFIRM,
        "complete": CONFIRM,
        "delete": CONFIRM,
    },
    "manage_notes": {
        "create": ALLOW,
        "search": ALLOW,
        "read": ALLOW,
        "append": CONFIRM,
        "delete": CONFIRM,
    },
    "manage_contacts": {
        "lookup": ALLOW,
        "add": CONFIRM,
        "update": CONFIRM,
    },
    "browser": {
        "search_web": ALLOW,
        "get_current_page": ALLOW,
        "open_url": ALLOW,
        "new_tab": ALLOW,
        "bookmark_current_page": CONFIRM,
    },
    "maps": {
        "search": ALLOW,
        "directions": ALLOW,
    },
}

_BROAD_TOOLS_REQUIRE_EXTRA_CHECK = {
    "finder",
    "manage_calendar",
    "execute_system_command",
}

_ALLOWED_URL_SCHEMES = {"http", "https", "maps"}
_BLOCKED_URL_SCHEMES = {"file", "javascript", "data", "applescript", "x-apple.systempreferences"}

_BLOCK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bchmod\s+777\b",
    r"\bchown\b",
    r"\bmkfs\b",
    r"\bdiskutil\b.*\b(erase|partition|unmount)\b",
    r"\bformat\b.*\bdisk\b",
    r"\berase\b.*\bdisk\b",
    r"\bdelete\b.*\ball\b.*\bfiles\b",
    r"\bdelete\b.*\beverything\b",
    r"\bkeychain\b",
    r"\bpasswords?\b",
    r"\bsecrets?\b",
    r"\bapi keys?\b",
    r"\btokens?\b",
    r"\bprivate keys?\b",
    r"\bsecurity settings?\b",
    r"\bdisable\b.*\bfirewall\b",
    r"\bturn off\b.*\bfirewall\b",
    r"\bgrant\b.*\b(full disk access|accessibility)\b",
    r"\bpay\b.*\b(invoice|bill|someone|person)\b",
    r"\bpurchase\b",
    r"\bbuy\b.*\b(now|this|it)\b",
]

_MODIFYING_INTENT_PATTERNS = [
    r"\b(delete|remove|cancel|erase|clear)\b",
    r"\b(rename|move|update|modify|reschedule)\b",
]

_SENSITIVE_DATA_PATTERNS = [
    r"\b(ssn|social security)\b",
    r"\bcredit card\b",
    r"\bbank\b.*\b(account|routing)\b",
    r"\bmedical\b",
    r"\btax\b",
    r"\blegal\b",
    r"\bprivate\b",
    r"\bconfidential\b",
]

_EXTERNAL_ACTION_TOOLS = {
    "send_imessage",
    "send_email",
    "start_facetime",
}


def _text(args: dict) -> str:
    return " ".join(str(v) for v in args.values() if v is not None).lower()


def _matches(patterns: list, text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _block(message: str = "I can't perform that action because it is too risky.") -> dict:
    return {"decision": BLOCK, "message": message}


def _allow() -> dict:
    return {"decision": ALLOW}


def _clarify(message: str) -> dict:
    return {"decision": CLARIFY, "message": message}


def _is_unsafe_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme in _BLOCKED_URL_SCHEMES:
        return True
    return bool(parsed.scheme and parsed.scheme not in _ALLOWED_URL_SCHEMES)


def _confirmation_intent(user_input: str) -> str:
    text = user_input.strip().lower()
    if not text:
        return "unknown"

    first_word = re.split(r"\s+", text, maxsplit=1)[0].strip(".,!?;:\"'()[]{}")
    if first_word in {"yes", "yeah", "yep", "sure", "confirm", "continue", "ok", "okay"}:
        return "approve"
    if first_word in {"no", "nope", "cancel", "stop"}:
        return "deny"
    if re.search(r"\b(go ahead|do it|sounds good|please do)\b", text):
        return "approve"
    if re.search(r"\b(don't|do not|never mind|nevermind)\b", text):
        return "deny"
    return "unknown"


def _describe(name: str, args: dict) -> str:
    if name == "send_imessage":
        return f"send an iMessage to {args.get('contact')}"
    if name == "send_email":
        return f"draft an email to {args.get('contact')}"
    if name == "start_facetime":
        return f"start a FaceTime call with {args.get('contact')}"
    if name == "manage_calendar":
        request = args.get("request")
        text = str(request).lower()
        if any(word in text for word in ("cancel", "delete", "remove")):
            target = _calendar_cancel_target(str(request))
            if target:
                day = " tomorrow" if "tomorrow" in text else " today" if "today" in text else _calendar_date_phrase(str(request))
                return f"delete the '{target}' Calendar event{day}"
            return f"cancel this Calendar event: {request}"
        if any(word in text for word in ("update", "move", "reschedule")):
            return f"update Calendar for: {request}"
        return f"use Calendar for: {request}"
    if name == "manage_contacts":
        return f"{args.get('action')} contact {args.get('name')}"
    if name == "manage_reminders":
        return f"{args.get('action')} reminder {args.get('task') or ''}".strip()
    if name == "manage_notes":
        return f"{args.get('action')} note {args.get('title') or ''}".strip()
    if name == "browser":
        return f"run Safari action {args.get('action')}"
    if name == "maps":
        return f"open Maps for {args.get('destination')}"
    if name == "finder":
        return f"run this Finder action: {args.get('task')}"
    if name == "execute_system_command":
        return f"run this system action: {args.get('task')}"
    return f"run {name}"


def _calendar_date_phrase(request: str) -> str:
    match = re.search(
        r"\b(?:on\s+)?((?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?)\b",
        str(request or ""),
        flags=re.IGNORECASE,
    )
    return f" on {match.group(1)}" if match else ""


def _calendar_cancel_target(request: str) -> str:
    text = str(request or "").strip()
    lower = text.lower()
    if not any(word in lower for word in ("cancel", "delete", "remove")):
        return ""
    if not any(word in lower for word in ("event", "meeting", "appointment")):
        return ""

    quoted = re.search(r"""["']([^"']+)["']""", text)
    if quoted:
        return quoted.group(1).strip()

    target = re.search(
        r"\b(?:event|meeting|appointment)\s+(?:called|named|about|for|with)?\s*(.+?)(?:\s+(?:today|tomorrow)\b.*|\s+(?:on\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?\b.*|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not target:
        return ""

    title = target.group(1).strip()
    title = re.sub(r"[.?!,;:]+$", "", title).strip()
    title = re.sub(r"^(my|the|a|an)\s+", "", title, flags=re.IGNORECASE).strip()
    if title.lower() in {"", "today", "tomorrow"}:
        return ""
    return title


def _calendar_needs_clarification(name: str, args: dict) -> bool:
    if name != "manage_calendar":
        return False
    request = str(args.get("request") or "")
    lower = request.lower()
    if not _matches(_MODIFYING_INTENT_PATTERNS, lower):
        return False
    if not any(word in lower for word in ("event", "meeting", "appointment")):
        return False
    if _calendar_cancel_target(request):
        return False
    return True


def _store_confirmation(name: str, args: dict) -> dict:
    global _PENDING_ACTION
    _PENDING_ACTION = {"name": name, "args": args}
    return {
        "decision": CONFIRM,
        "message": f"Before I {_describe(name, args)}, should I continue?",
    }


def has_pending_action() -> bool:
    return _PENDING_ACTION is not None


def resolve_confirmation(user_input: str) -> dict:
    global _PENDING_ACTION
    if _PENDING_ACTION is None:
        return {"matched": False}

    intent = _confirmation_intent(user_input)
    if intent == "approve":
        action = _PENDING_ACTION
        _PENDING_ACTION = None
        return {"matched": True, "approved": True, **action}
    if intent == "deny":
        action = _PENDING_ACTION
        _PENDING_ACTION = None
        return {
            "matched": True,
            "approved": False,
            "message": f"Cancelled. I did not {_describe(action['name'], action['args'])}.",
        }
    return {"matched": False}


def check_policy(name: str, args: dict) -> dict:
    arg_text = _text(args)
    if _matches(_BLOCK_PATTERNS, arg_text):
        return _block()

    if name == "browser" and _is_unsafe_url(args.get("url", "")):
        return _block("I can't open that URL because the scheme is unsafe.")

    if name in _EXTERNAL_ACTION_TOOLS:
        return _store_confirmation(name, args)

    if name in {"web_search", "manage_notes", "finder", "execute_system_command"} and _matches(_SENSITIVE_DATA_PATTERNS, arg_text):
        return _store_confirmation(name, args)

    if _calendar_needs_clarification(name, args):
        return _clarify("Which Calendar event should I cancel?")

    tool_decision = _TOOL_POLICIES.get(name)
    if tool_decision == ALLOW:
        return _allow()
    if tool_decision == CONFIRM:
        return _store_confirmation(name, args)
    if tool_decision == BLOCK:
        return _block()

    action_policy = _ACTION_POLICIES.get(name)
    if action_policy:
        decision = action_policy.get(args.get("action"), CONFIRM)
        if decision == ALLOW:
            return _allow()
        if decision == CONFIRM:
            return _store_confirmation(name, args)
        if decision == BLOCK:
            return _block()

    if name in _BROAD_TOOLS_REQUIRE_EXTRA_CHECK:
        if _matches(_MODIFYING_INTENT_PATTERNS, arg_text):
            return _store_confirmation(name, args)
        return _allow()

    # Unknown tools default to confirm. That keeps newly added tools from becoming
    # executable without an explicit policy decision.
    return _store_confirmation(name, args)

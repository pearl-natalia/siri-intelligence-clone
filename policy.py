import re


_PENDING_ACTION = None

_YES = {"yes", "yeah", "yep", "sure", "confirm", "do it", "go ahead", "continue"}
_NO = {"no", "nope", "cancel", "stop", "don't", "do not"}

_BLOCKED_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bformat\b.*\bdisk\b",
    r"\berase\b.*\bdisk\b",
    r"\bdelete\b.*\ball\b.*\bfiles\b",
    r"\bdelete\b.*\beverything\b",
    r"\bkeychain\b",
    r"\bpasswords?\b",
    r"\bsecrets?\b",
    r"\bsecurity settings?\b",
]

_DESTRUCTIVE_PATTERNS = [
    r"\bdelete\b",
    r"\bremove\b",
    r"\bcancel\b",
    r"\berase\b",
    r"\bclear\b",
    r"\brename\b",
    r"\bmove\b",
    r"\bupdate\b",
    r"\bmodify\b",
    r"\breschedule\b",
]


def _text(args: dict) -> str:
    return " ".join(str(v) for v in args.values() if v is not None).lower()


def _matches(patterns: list, text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _describe(name: str, args: dict) -> str:
    if name == "send_imessage":
        return f"send an iMessage to {args.get('contact')}"
    if name == "send_email":
        return f"draft an email to {args.get('contact')}"
    if name == "start_facetime":
        return f"start a FaceTime call with {args.get('contact')}"
    if name == "manage_calendar":
        return f"modify Calendar for: {args.get('request')}"
    if name == "manage_contacts":
        return f"{args.get('action')} contact {args.get('name')}"
    if name == "finder":
        return f"run this Finder action: {args.get('task')}"
    if name == "execute_system_command":
        return f"run this system action: {args.get('task')}"
    return f"run {name}"


def has_pending_action() -> bool:
    return _PENDING_ACTION is not None


def resolve_confirmation(user_input: str) -> dict:
    global _PENDING_ACTION
    if _PENDING_ACTION is None:
        return {"matched": False}

    normalized = user_input.strip().lower()
    if normalized in _YES:
        action = _PENDING_ACTION
        _PENDING_ACTION = None
        return {"matched": True, "approved": True, **action}
    if normalized in _NO:
        action = _PENDING_ACTION
        _PENDING_ACTION = None
        return {
            "matched": True,
            "approved": False,
            "message": f"Cancelled. I did not {_describe(action['name'], action['args'])}.",
        }
    return {"matched": False}


def check_policy(name: str, args: dict) -> dict:
    global _PENDING_ACTION

    arg_text = _text(args)
    if _matches(_BLOCKED_PATTERNS, arg_text):
        return {
            "decision": "block",
            "message": "I can't perform that action because it is too risky.",
        }

    if name in {"get_weather", "get_time"}:
        return {"decision": "allow"}

    if name == "control_music":
        return {"decision": "allow"}

    if name == "create_reminder":
        return {"decision": "allow"}

    if name in {"send_imessage", "send_email", "start_facetime"}:
        _PENDING_ACTION = {"name": name, "args": args}
        return {
            "decision": "confirm",
            "message": f"Before I {_describe(name, args)}, should I continue?",
        }

    if name == "manage_contacts" and args.get("action") in {"add", "update"}:
        _PENDING_ACTION = {"name": name, "args": args}
        return {
            "decision": "confirm",
            "message": f"Before I {_describe(name, args)}, should I continue?",
        }

    if name in {"finder", "manage_calendar", "execute_system_command"} and _matches(_DESTRUCTIVE_PATTERNS, arg_text):
        _PENDING_ACTION = {"name": name, "args": args}
        return {
            "decision": "confirm",
            "message": f"Before I {_describe(name, args)}, should I continue?",
        }

    return {"decision": "allow"}

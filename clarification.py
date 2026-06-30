from difflib import SequenceMatcher


_PENDING = None


def _full_name(contact: dict) -> str:
    return f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()


def _score(query: str, contact: dict) -> float:
    query = query.lower().strip()
    full = _full_name(contact).lower()
    first = contact.get("first_name", "").lower()
    last = contact.get("last_name", "").lower()
    if query == full or query == first or query == last:
        return 1.0
    if query in full:
        return 0.92
    return SequenceMatcher(None, query, full).ratio()


def contact_candidates(query: str, contacts: list, limit: int = 5) -> list:
    scored = []
    for contact in contacts:
        score = _score(query, contact)
        if score >= 0.55:
            scored.append((score, contact))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [contact for _, contact in scored[:limit]]


def needs_contact_clarification(query: str, candidates: list) -> bool:
    if len(candidates) <= 1:
        return False
    query = query.lower().strip()
    exact = [
        c for c in candidates
        if query == _full_name(c).lower()
        or query == c.get("first_name", "").lower()
        or query == c.get("last_name", "").lower()
    ]
    return len(exact) != 1


def ask_contact(action_name: str, args: dict, contact_field: str, candidates: list) -> dict:
    global _PENDING
    _PENDING = {
        "kind": "contact",
        "action_name": action_name,
        "args": args,
        "contact_field": contact_field,
        "candidates": candidates,
    }
    names = ", ".join(_full_name(c) for c in candidates)
    return {
        "success": False,
        "message": f"I found multiple matching contacts: {names}. Which one did you mean?",
    }


def resolve(user_input: str) -> dict:
    global _PENDING
    if _PENDING is None:
        return {"matched": False}

    query = user_input.strip()
    candidates = _PENDING["candidates"]
    exact = [
        c for c in candidates
        if query.lower() == _full_name(c).lower()
    ]
    matches = exact or contact_candidates(query, candidates, limit=2)
    if len(matches) != 1:
        names = ", ".join(_full_name(c) for c in candidates)
        return {
            "matched": True,
            "resolved": False,
            "message": f"I still need you to pick one of these contacts: {names}.",
        }

    pending = _PENDING
    _PENDING = None
    selected = _full_name(matches[0])
    args = dict(pending["args"])
    args[pending["contact_field"]] = selected
    return {
        "matched": True,
        "resolved": True,
        "action_name": pending["action_name"],
        "args": args,
    }

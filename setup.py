import json, os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

QUESTIONS = [
    ("user_first_name", "What's your first name? "),
    ("user_last_name",  "What's your last name? "),
    ("llm name",        "What would you like to call your assistant? (default: Swift) ", "Swift"),
    ("default_browser", "Default browser — Chrome, Safari, or Firefox? (default: Chrome) ", "Chrome"),
]

def run():
    print("\nWelcome to Swift setup.\n")

    existing = {}
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            existing = json.load(f)
        print("Existing settings found. Press Enter to keep current value.\n")

    settings = dict(existing)

    for key, prompt, *default in QUESTIONS:
        current = existing.get(key, default[0] if default else "")
        hint = f"[{current}] " if current else ""
        value = input(f"{prompt}{hint}").strip()
        settings[key] = value if value else current

    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=4)

    print(f"\nAll set! Say 'Hey Swift' to get started.\n")

if __name__ == "__main__":
    run()

"""Writable locations for the source checkout and packaged Mac app."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def data_dir():
    override = os.getenv('SWIFT_DATA_DIR')
    if override:
        return Path(override).expanduser()
    if getattr(sys, 'frozen', False):
        return Path.home() / 'Library' / 'Application Support' / 'Swift'
    return ROOT

def settings_path():
    return data_dir() / 'settings.json'

def load_settings():
    defaults = {'user_first_name': '', 'user_last_name': '', 'llm name': 'Swift', 'default_browser': 'Chrome'}
    try:
        values = json.loads(settings_path().read_text())
        if isinstance(values, dict):
            defaults.update(values)
    except (OSError, ValueError):
        pass
    return defaults

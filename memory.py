"""Per-user local memory for the downloadable app.

Existing source checkouts with Chroma data keep using their original backend.
The packaged app uses SQLite and doesn't carry the legacy embedding stack.
"""
import importlib
import re
import sqlite3
import sys
from datetime import datetime, timezone
from runtime_paths import data_dir

TOP_K = 5

def _legacy():
    if not getattr(sys, 'frozen', False) and (data_dir() / 'memory_db').exists():
        return importlib.import_module('memory_legacy')
    return None

def _connect():
    data_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(data_dir() / 'memory.sqlite3')
    connection.execute('CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, text TEXT NOT NULL, normalized TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL)')
    connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS facts_search USING fts5(text, content="facts", content_rowid="id")')
    connection.execute('CREATE TRIGGER IF NOT EXISTS facts_insert AFTER INSERT ON facts BEGIN INSERT INTO facts_search(rowid,text) VALUES (new.id,new.text); END')
    return connection

def save_facts(facts):
    with _connect() as connection:
        for fact in facts:
            text = re.sub(r'\s+', ' ', fact).strip()[:1000]
            if text:
                connection.execute('INSERT OR IGNORE INTO facts(text,normalized,created_at) VALUES (?,?,?)',
                                   (text, text.casefold(), datetime.now(timezone.utc).isoformat()))

def save_session(history):
    legacy = _legacy()
    if legacy:
        return legacy.save_session(history)
    if len(history) < 2:
        return
    from model import model
    conversation = '\n'.join(f"{entry['role']}: {entry['content']}" for entry in history)
    response = model('Extract only concrete user preferences and facts from this conversation. Return one fact per line, without bullets. Ignore greetings and one-off commands. Return an empty response if there are no lasting facts.\n\n' + conversation, 0.0)
    save_facts(response.splitlines())

def load_context(query):
    legacy = _legacy()
    if legacy:
        return legacy.load_context(query)
    terms = list(dict.fromkeys(re.findall(r'\w{3,}', query.casefold())))[:20]
    if not terms:
        return ''
    # Only quoted word tokens enter FTS syntax; values are SQL parameters.
    match = ' OR '.join('"' + term + '"' for term in terms)
    with _connect() as connection:
        rows = connection.execute('SELECT text FROM facts_search WHERE facts_search MATCH ? ORDER BY rank LIMIT ?', (match, TOP_K)).fetchall()
    return 'Facts about the user:\n' + '\n'.join(row[0] for row in rows) if rows else ''

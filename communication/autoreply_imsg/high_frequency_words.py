import sys, os, sqlite3
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from model import model  

def add_high_freq_words(phone_number, input_text, db_path='high_frequency_words.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS phrase_counts (
        phrase_count_id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id INTEGER,
        phrase TEXT,
        count INTEGER,
        FOREIGN KEY (contact_id) REFERENCES contacts (contact_id)
    );
    ''')

    prompt = f"""Identify universal phrases, emojis, or prompts that can be used later to generate message replies that mimic the user's style. Output in a comma separated list. Output in lowercase.
    
    </EXAMPLE>
        <INPUT>Yo, I saw your message, and it's all good! Let's link up at 2 PM on Tuesday. Hit me up if you need anything, fam.</INPUT>
        <OUTPUT>yo, it's all good!, link up, hit me up, fam</OUTPUT>
    </EXAMPLE>

    Here is the input: {input_text}
    """
    output = model(prompt, 0.7)
    phrases = [phrase.strip() for phrase in output.split(',') if phrase.strip()]

    cursor.execute('INSERT OR IGNORE INTO contacts (name) VALUES (?)', (phone_number,))
    cursor.execute('SELECT contact_id FROM contacts WHERE name = ?', (phone_number,))
    contact_id = cursor.fetchone()[0]

    phrase_counter = Counter(phrases)
    for phrase, count in phrase_counter.items():
        cursor.execute('SELECT count FROM phrase_counts WHERE contact_id = ? AND phrase = ?', (contact_id, phrase))
        result = cursor.fetchone()
        if result:
            cursor.execute('UPDATE phrase_counts SET count = ? WHERE contact_id = ? AND phrase = ?', 
                           (result[0] + count, contact_id, phrase))
        else:
            cursor.execute('INSERT INTO phrase_counts (contact_id, phrase, count) VALUES (?, ?, ?)', 
                           (contact_id, phrase, count))

    cursor.execute('''
    DELETE FROM phrase_counts 
    WHERE phrase_count_id IN (
        SELECT phrase_count_id FROM phrase_counts
        WHERE contact_id = ?
        ORDER BY count ASC, phrase_count_id ASC
        LIMIT (
            SELECT MAX(COUNT(*) - 10, 0) 
            FROM phrase_counts 
            WHERE contact_id = ?
        )
    )
    ''', (contact_id, contact_id))

    conn.commit()
    conn.close()

def get_high_freq_words(phone_number, db_path='high_frequency_words.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT contact_id FROM contacts WHERE name = ?', (phone_number,))
    contact_id = cursor.fetchone()

    if not contact_id:
        conn.close()
        return []

    contact_id = contact_id[0]
    
    cursor.execute('''
    SELECT phrase, count FROM phrase_counts
    WHERE contact_id = ?
    ORDER BY count DESC
    ''', (contact_id,))
    
    result = cursor.fetchall()
    conn.close()
    
    return result

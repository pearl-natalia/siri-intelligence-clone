import sqlite3, os, datetime, re

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")

def apple_timestamp_to_datetime(timestamp):
    """ Convert Apple's iMessage timestamp to a readable datetime. """
    if timestamp:
        return datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=timestamp / 1e9)
    return None

def clean_receiving_msg(attributed_body):
    """ Extract readable text from attributedBody and remove system junk. """
    if isinstance(attributed_body, bytes):
        decoded_text = attributed_body.decode('utf-8', errors='ignore')

        # Remove common system prefixes like "streamtyped@..."
        clean_text = re.sub(r'streamtyped@[^\s]+', '', decoded_text)

        # Remove known Apple metadata keys like NSDictionary, NSNumber, etc.
        clean_text = re.sub(r'NSDictionary[^\s]+', '', clean_text)
        clean_text = re.sub(r'__kIMMessagePartAttributeNam[^\s]+', '', clean_text)
        clean_text = re.sub(r'NSNumber[^\s]+', '', clean_text)
        clean_text = re.sub(r'NSValue[^\s]+', '', clean_text)

        # Remove random trailing characters (like 'td*', 'iI', etc.)
        clean_text = re.sub(r'\b\w{1,2}\*\b', '', clean_text)  # Remove short junk words ending with '*'
        clean_text = re.sub(r'\biI\b', '', clean_text)  # Remove "iI" at the end

        # Remove extra spaces caused by cleaning
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text if clean_text else "⚠️ [No Text Content]"
    
    return attributed_body

def clean_sending_msg(text):
    cleaned_text = re.sub(r'[^\x20-\x7E]', '', text)
    cleaned_text = cleaned_text.strip()
    pattern = r"streamtyped@(?:[A-Za-z]+)+\+?"
    cleaned_text = re.sub(pattern, '', cleaned_text)
    return cleaned_text



def get_recent_imessages(contact_number, limit=5):
    """ Fetch recent iMessages to/from the given phone number. """
    if not os.path.exists(DB_PATH):
        print("❌ Error: chat.db not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
    SELECT message.text, message.attributedBody, message.date, message.is_from_me
    FROM message
    JOIN handle ON message.handle_id = handle.ROWID
    WHERE handle.id = ?
    ORDER BY message.date DESC
    LIMIT ?;
    """

    cursor.execute(query, (contact_number, limit))
    messages = cursor.fetchall()
    conn.close()

    if not messages:
        print("⚠️ No recent messages found.")
        return
    

    # print(f"📨 Recent messages with {contact_number}:\n")
    message_list = []
    for text, attributed_body, date, is_from_me in messages:
        sender = "me:" if is_from_me else "friend:"
            
        message_text = text if text else clean_receiving_msg(attributed_body) or "⚠️ [No Text Content]"

        if sender == "me:":
            message_text = clean_sending_msg(message_text)
        
        message_text = message_text.strip()

        timestamp = apple_timestamp_to_datetime(date)
        message_list.append({
            'Time': [f'{timestamp}'],
            'Sender': sender,
            'Message': message_text
        })
    
    return message_list[::-1]

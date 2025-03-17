import time, sys, os, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from retrieve_message import get_recent_imessages
from autoreply_imsg.generate_reply import generate_reply
from dotenv import load_dotenv

LIMIT = 5
LAST_MSG = None  # Track the last message

def generate_apple_script(phone_number, msg):
    apple_script = f"""
                    tell application "Messages"
                    set phoneNumber to "{phone_number}"
                    set targetService to 1st service whose service type is iMessage
                    set targetBuddy to buddy phoneNumber of targetService
                    send "{msg}" to targetBuddy
                    end tell
                    """
    return apple_script

def main():
    load_dotenv()
    phone_number = os.environ.get("PHONE_NUMBER")

    if not phone_number:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    global LAST_MSG
    while True:
        # Get recent iMessages for the given phone number
        msgs = get_recent_imessages(phone_number, limit=LIMIT)
        print(msgs[-1])
        
        # Check if there's a new message (compare the latest message)
        if msgs and msgs[-1] != LAST_MSG and msgs[-1]['Sender'] != "me:":
            print("New message detected!")
            LAST_MSG = msgs[-1]  # Update the last message
            reply = generate_reply(phone_number, msgs).rstrip('\n')
            print(reply) # Call generate.py
            subprocess.run(['osascript', '-e', generate_apple_script(phone_number, reply)])

        # Sleep for a specified time before checking again (e.g., 5 seconds)
        time.sleep(10)

if __name__ == "__main__":
    main()

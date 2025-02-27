import time
from e import get_recent_imessages
from generate import generate_reply
import subprocess

PHONE_NUMBER = "+16479734401"
PHONE_NUMBER_2 = "+16478703357"
# PHONE_NUMBER = "+14165564596"
LIMIT = 5
LAST_MSG = None  # Track the last message

def generate_apple_script(phone_number, msg):
    apple_script = f'''
    tell application "Messages"
        set phoneNumber to "{phone_number}"
        set targetService to 1st service whose service type is iMessage
        set targetBuddy to buddy phoneNumber of targetService
        send "{msg}" to targetBuddy
    end tell
    '''
    return apple_script

def main():
    global LAST_MSG
    while True:
        # Get recent iMessages for the given phone number
        msgs = get_recent_imessages(PHONE_NUMBER, limit=LIMIT)
        print(msgs[-1])
        
        # Check if there's a new message (compare the latest message)
        if msgs and msgs[-1] != LAST_MSG and msgs[-1]['Sender'] != "me:":
            print("New message detected!")
            LAST_MSG = msgs[-1]  # Update the last message
            reply = generate_reply(msgs).rstrip('\n')
            print(reply) # Call generate.py
            subprocess.run(['osascript', '-e', generate_apple_script(PHONE_NUMBER, reply)])

        # Sleep for a specified time before checking again (e.g., 5 seconds)
        time.sleep(10)

if __name__ == "__main__":
    main()

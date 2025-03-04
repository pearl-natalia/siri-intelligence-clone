import subprocess, sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from model import model
from communication.find_contact import name_to_phone_number

def facetime(contact):
    prompt = f"""
                Your job is to take the following contact: {contact} 
                and determine if it is a phone number. 
                If it is a phone number, return 'phone number'.
                If it is not a phone number, return 'name'. 
                Return either 'phone number' or 'name' in all lowercase letters. Do not return any additional text.

                <EXAMPLE>
                    <INPUT>
                        Contact: Rajan
                    </Input>
                    <OUTPUT>
                        name
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Contact: +12345678900
                    </Input>
                    <OUTPUT>
                        phone number
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Contact: Apples are a fruit
                    </Input>
                    <OUTPUT>
                        name
                    </OUTPUT>
                </EXAMPLE>

                Here is the input contact: {contact}
            """
    
    model_response = model(prompt, 1).lower().strip()
    if model_response == 'name':
        phone_number = name_to_phone_number(contact)
    else:
        phone_number = model_response

    apple_script = f"""
                    do shell script "open facetime://{phone_number}"
                    delay 2
                    tell application "System Events"
                    tell process "FaceTime"
                    set frontmost to true
                    tell window 1
                    repeat while not (exists button "Call")
                    delay 1
                    end repeat
                    click button "Call"
                    end tell
                    end tell
                    end tell
                    """
    
    # Trigger facetime
    subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()

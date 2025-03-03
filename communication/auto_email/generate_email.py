import subprocess, sys, os, json, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from model import model
from communication.find_contact import get_email
from datetime import datetime

def generate_email(content):

    # Get contact
    prompt = f"""
                Your job is to extract the name, email, or phone number of the person the user wants to send the info to. Only return the name, email, or phone number with no additional text. If more than 1 form of contact is provided, return one of email, name, phone number in that order of availability.
                <EXAMPLE>
                    <INPUT>
                    Send an email to Sarah that I will be late for work tmrw.
                    </INPUT>
                    <OUTPUT>
                    Sarah
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                    Send an email to Mick that I will be late for work tmrw. His email is mick@gmail.com.
                    </INPUT>
                    <OUTPUT>
                    mick@gmail.com
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                    Send an email to +1234567890 that I will be late for work tmrw. Their name is Luis Gerad.
                    </INPUT>
                    <OUTPUT>
                    Luis Gerad
                    </OUTPUT>
                </EXAMPLE>

                Here is the input: {content}
            """

    contact = model(prompt, 1).strip()

    # Context
    current_datetime = datetime.now()
    curr_date = current_datetime.date()
    curr_time = current_datetime.time()

    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    json_file_path = os.path.join(parent_dir, 'settings.json')
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    first_name = data["user_first_name"]
    last_name = data["user_last_name"]

    # Generate email content
    prompt =f"""
            You are an expert email generator. 
            Your job is to generate a suitable subject line and email based on the following content: {content}. If you can't determine the name of who this email is being sent to, set the greeting to 'Hello,'
            Keep it concise. Determine the tone (friendly/casual vs professional) based on the content being emailed. Determine how professional while maintaining professionalism. Have a salutation, introduction, body, closing, and email signature with the users full name: {first_name} {last_name}.
            Here is the output format, do not include any additional text:

            <OUTPUT FORMAT>
                subject: <subject>
                email: <email>
            </OUTPUT FORMAT>

            <EXAMPLE>
                <INPUT> 
                    Send an email to Jenny reminding her that we have a meeting via zoom tmrw at 9am.
                </INPUT>
                <OUTPUT>
                    subject: Meeting Reminder for Tomorrow at 9 AM via Zoom
                    email: 
                    Dear Jenny,
                    I hope this message finds you well. I wanted to kindly remind you that we have a scheduled meeting tomorrow, February 29th at 9 AM via Zoom.

                    Please let me know if there are any changes or additional information needed. I look forward to our discussion.

                    Best regards,
                    John Doe
                </OUTPUT>
            </EXAMPLE>
            <EXAMPLE>
                <INPUT> 
                    Send an email to 1234567890 reminding her that we have a meeting via zoom tmrw at 9am.
                </INPUT>
                <OUTPUT>
                    subject: Meeting Reminder for Tomorrow at 9 AM via Zoom
                    email: 
                    Hello,
                    I hope this message finds you well. I wanted to kindly remind you that we have a scheduled meeting tomorrow, February 29th at 9 AM via Zoom.

                    Please let me know if there are any changes or additional information needed. I look forward to our discussion.

                    Best regards,
                    John Doe
                </OUTPUT>
            </EXAMPLE>

            Side note: today's date is {curr_date} and the current time is {curr_time}. Use this info if needed.
            """
   
    response = model(prompt, 1.5).strip()
    subject_match = re.search(r"subject:\s*(.*?)\s*email:", response, re.DOTALL | re.IGNORECASE)
    subject = subject_match.group(1).strip() if subject_match else ""

    # Extracting email
    email_match = re.search(r"email:\s*(.*)", response, re.DOTALL | re.IGNORECASE)
    email_content = email_match.group(1).strip() if email_match else ""

    # Get email
    email = get_email(contact)
    if email is None:
        email == ""

    # Draft email
    apple_script = f"""
                    tell application "Mail" 
                    set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{email_content}", visible:true}}  
                    tell newMessage 
                    make new recipient at end of to recipients with properties {{address:"{email}"}}  
                    end tell  
                    activate  
                    end tell
                    """
    
    # Trigger facetime
    subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    generate_email("Send an email to Elie that I will be late for work.")
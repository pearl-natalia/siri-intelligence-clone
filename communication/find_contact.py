import subprocess, re, os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model import model

def get_contact_list():
    apple_script =  """
                    tell application "Contacts"
                    set contactNames to ""
                    repeat with c in people
                    set contactNames to contactNames & first name of c & "," & last name of c & linefeed
                    end repeat
                    return contactNames
                    end tell
                    """
    
    contact_list = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()
    contact_dict = []
    if contact_list:
        contacts = contact_list.splitlines()
        for contact in contacts:
            first_name, last_name = contact.split(",", 1)
            if last_name == "missing value":
                last_name = ""
            contact_dict.append({
            'first_name': first_name,
            'last_name': last_name
            })
    else:
        print("No contacts found.")
    return contact_dict

def find_similar_contact(name):
    contact_list = get_contact_list()
    prompt =    f"""   
                Your job is to return the contact that is most similar to the following name: {name}.
                Go through my contact list and extract the first and last name from the list and return it, in a 'first name, last name' format. 
                If last name is empty in the list, then return 'first name, ""'. Output names exactly as is in contacts. If no similar match, output 'No match'. Only output the name or 'No match', no other text else.

                <EXAMPLE>
                    <INPUT>
                    Name: rajan
                    Contact List: {{first_name: Rajan, last_name: Agarwal}}, {{first_name: Raja, last_name: ""}}
                    </INPUT>

                    <OUTPUT>
                    Rajan, Agarwal
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                    Name: pearl Natalia
                    Contact List: {{first_name: Pearl, last_name: ""}}, {{first_name: Patty, last_name: "Natalia"}}
                    </INPUT>

                    <OUTPUT>
                    Pearl, ""
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                    Name: sandra
                    Contact List: {{first_name: Sarah, last_name: ""}}, {{first_name: "Sierra", last_name: "Natalia"}}
                    </INPUT>

                    <OUTPUT>
                    No match
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                    Name: raj
                    Contact List: {{first_name: Rajan, last_name: Agarwal}}, {{first_name: Raja, last_name: ""}}
                    </INPUT>

                    <OUTPUT>
                    Raja, ""
                    </OUTPUT>
                </EXAMPLE>


                Here is the information:
                Name: {name},
                Contact: {contact_list}
                """
    return model(prompt, 1)


def get_phone_number(first_name, last_name):
    if last_name == '""' or last_name is None:
        apple_script = f"""
                        tell application "Contacts"
                        set matchingContacts to people whose first name is "{first_name}"
                        if (count of matchingContacts) > 0 then
                        set targetContact to first item of matchingContacts
                        set contactDetails to ""
                        repeat with phoneNumber in (get value of phones of targetContact)
                        set contactDetails to contactDetails & phoneNumber & linefeed
                        end repeat
                        return contactDetails
                        else
                        return "No contact found"
                        end if
                        end tell
                        """
    else:
        apple_script = f"""
                        tell application "Contacts"
                        set matchingContacts to people whose first name is "{first_name}" and last name is "{last_name}"
                        if (count of matchingContacts) > 0 then
                        set targetContact to first item of matchingContacts
                        set contactDetails to ""
                        repeat with phoneNumber in (get value of phones of targetContact)
                        set contactDetails to contactDetails & phoneNumber & linefeed
                        end repeat
                        return contactDetails
                        else
                        return "No contact found"
                        end if
                        end tell
                        """

    result = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()
    
    return result if "No contact found" not in result else None

def name_to_email(first_name, last_name):
    apple_script =  f"""
                    tell application "Contacts"
                    set firstName to "{first_name}" 
                    set lastName to "{last_name}"
                    if lastName is "" then
                    set matchingContacts to people whose first name is firstName
                    else
                    set matchingContacts to people whose first name is firstName and last name is lastName
                    end if
                    if (count of matchingContacts) > 0 then
                    set contactEmail to value of email of first item of matchingContacts
                    return contactEmail
                    else
                    return "No contact found"
                    end if
                    end tell
                    """
    
    email = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()
    return email

def phone_number_to_email(phone_number):
    # Find matching phone number
    apple_script =  """
                    tell application "Contacts" to get value of phones of every person
                    """
    
    raw_phone_number_list = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()

    def normalize_number(number):
        digits = re.sub(r'\D', '', number)
        if len(digits) > 10:
            digits = digits[1:]
        return digits

    normalized_phone_number_list = [normalize_number(num) for sublist in raw_phone_number_list for num in sublist]
    normalized_phone_number = normalize_number(phone_number)
    for i in range(len(normalized_phone_number_list)):
        if normalized_phone_number_list[i] == normalized_phone_number:
            phone_number = raw_phone_number_list[i]
            break
    
    apple_script =  f"""
                    tell application "Contacts"
                    set phoneNumber to "{phone_number}"
                    set matchingContacts to people whose value of phones contains phoneNumber
                    if (count of matchingContacts) > 0 then
                    set contactEmail to value of email of first item of matchingContacts
                    return contactEmail
                    else
                    return "No contact found"
                    end if
                    end tell
                    """
    
    email = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()
    return email

def get_email(contact):
    prompt = f"""
                Your job is to take the following contact: {contact} 
                and determine if it is an email, phone number, or name. 
                If it is a phone number, return 'phone number'. If it is an email, return 'email'. Otherwise, return 'name'.
                 
                Return either 'phone number', 'name', or 'name' in all lowercase letters. Do not return any additional text.

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

                <EXAMPLE>
                    <INPUT>
                    Contact: abc@outlook.com
                    </Input>
                    <OUTPUT>
                    email
                    </OUTPUT>
                </EXAMPLE>

                Here is the input contact: {contact}
            """
    
    model_response = model(prompt, 1).lower().strip()
    if model_response == 'name':
        similar_name = find_similar_contact(contact)
        first_name, last_name = [item.strip() for item in similar_name.split(",")]
        if last_name == '""':
            last_name = ""
        email = name_to_email(first_name, last_name)
        if email == "No contact found":
            return None
    elif model_response == 'phone number':
        email = phone_number_to_email(contact)
        if email == "No contact found":
            return None
    else:
        email = contact
    return email


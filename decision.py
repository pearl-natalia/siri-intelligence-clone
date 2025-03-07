import sys, json
from datetime import datetime
from system.music import music
from system.system import adjust_system, world_clock, get_location
from system.weather import weather
from system.auto_calendar import calendar
from transcription.speech import speech
from transcription.transcribe import transcribe
from model import model, add_user_message, add_assistant_message, get_history

def get_content(silence_duration=-1):
    # if silence_duration != -1:
    #     transcribe(SILENCE_DURATION=silence_duration)
    # else:
    #     transcribe()
    with open("transcription/transcription.txt", "r") as file:
        content = file.read().strip()
    if content=="":
        return None
    return content

def previous_user_message():
    user_message = None
    counter = 3
    for message in reversed(get_history()):
        if message["role"] == "user" and message["content"]!="" and message["content"] is not None:
            user_message = message["content"]
            return True
        counter -=1
        if counter==0:
            break
    return False

def decision():
    with open('settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)

    # Attempt 1
    content = get_content()
    
    # No response
    if content is None:
        # Attempt 2
        if previous_user_message() is False:
            speech(f"What can I do for you, {json_data['user_first_name']}?")
        else:
            speech(f"Sorry, I didn't get that. Could you please repeat yourself?")
        content = get_content(3)
        
        if content is None:
            if previous_user_message() is True:
                sys.exit()
            else:
                # Attempt 3
                speech(f"Sorry, I didn't get that. Could you please repeat yourself?")
                content = get_content(3)
                if content is None:
                    sys.exit()
    
    add_user_message(content)

    # Determine the action
    prompt = f"""
            You will take the user's transcription and determine the category that their action belongs in. 
            Here is the input transcription: {content}.
            Output 'communication' if the action involes messages, emails, or facetime calls. 
            Output 'weather' if the action involes weather information.
            Output 'time' if the action involes checking the time.
            Output 'song' if the action involves playing, pausing, opening, etc music. The prompt should include key words like 'play' but don't need to include key words like 'song' for the category to be 'song'.
            Output 'calendar' if the action involes schedules, events, calendars, etc.
            Output 'notes' if the action requires generating text (i.e lists, essays, recipes, etc) that would be best suited to be written in the notes app.
            Output 'system' if the action can be executed with osa (apple) scripts via the terminal (i.e. directions) and doesn't involve emails, messages, songs, weather, calendar, notes, nor facetiming/phone calls. This includes generating long text (i.e. essays, paragraphs, etc), which will be written in the notes app.
            Otherwise, output 'llm'.
            Only output either 'communication', 'weather', 'time', 'song', 'calendar', 'notes', 'system', or 'llm' in all lowercase. Do not output any additional text.

            <EXAMPLE>
                <INPUT> 
                    Send an email to Jenny reminding her that we have a meeting via zoom tmrw at 9am.
                </INPUT>
                <OUTPUT>
                    communication
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    How cold is it tomorrow?
                </INPUT>
                <OUTPUT>
                    weather
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Find me a cookie recipe.
                </INPUT>
                <OUTPUT>
                    system
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Write me an essay about flowers.
                </INPUT>
                <OUTPUT>
                    notes
                </OUTPUT>
            </EXAMPLE>


            <EXAMPLE>
                <INPUT> 
                    Play Shape of You.
                </INPUT>
                <OUTPUT>
                    song
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Generate a cookie recipe.
                </INPUT>
                <OUTPUT>
                    llm
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Tell me a funny story.
                </INPUT>
                <OUTPUT>
                    llm
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Time in san fransisco
                </INPUT>
                <OUTPUT>
                    time
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    What's my schedule like tomorrow?
                </INPUT>
                <OUTPUT>
                    calendar
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT> 
                    Charge my computer.
                </INPUT>
                <OUTPUT>
                    llm
                </OUTPUT>
            </EXAMPLE>
            """
    
    category = model(prompt, 1.5)
    print(category)
    if category == "system":
        generate_prompt = f"Generate me a short, concise response to the user's input: {content}"
    elif category == "song":
        generate_prompt = f"Generate me a short, concise response to the user's input: {content}. Something like 'now playing <song name> on spotify."
    elif category == "llm":
        generate_prompt = f"Generate a friendly 1-2 sentence response to the user's input: {content}. Make sure it's not too long. Your job is to continue the conversation."
    elif category == "notes":
        generate_prompt = f"Generate a friendly 1-2 sentence response to the user's input: {content}. Make sure not to output the generated text itself, and just mention that it was written in the notes app."


    else: # messages, facetime, or email
        generate_prompt = ""

    response_prompt =   f""" 
                        You are an expert ai voice assistant. {generate_prompt}. Here is some additional info if needed: {json_string}.
                        Only output the response and no additional text. This output will be converted to speech and played as audio for the user to listen to. Assume time, date, and current location information already provided and don't request these details from user.
                        Here is the date {datetime.now().date()} and time {datetime.now().time()} and current location {get_location()} if needed in the response.

                        <EXAMPLE>
                            <INPUT> 
                                Find me a cookie recipe.
                            </INPUT>
                            <OUTPUT>
                                Here is a cookie recipe I found on the internet.
                            </OUTPUT>
                        </EXAMPLE>

                        <EXAMPLE>
                            <INPUT> 
                                Charge my computer.
                            </INPUT>
                            <OUTPUT>
                                I can't do that unfortunately.
                            </OUTPUT>
                        </EXAMPLE>

                        <EXAMPLE>
                            <INPUT> 
                                Turn the volume up.
                            </INPUT>
                            <OUTPUT>
                                I turned the volume up!
                            </OUTPUT>
                        </EXAMPLE>

                        <EXAMPLE>
                            <INPUT> 
                                Directions to Vaughan Mills.
                            </INPUT>
                            <OUTPUT>
                                Directions have been entered.
                            </OUTPUT>
                        </EXAMPLE>
                        """
    
    if category != "weather" and category != "time": #no response needed if weather
        response = model(response_prompt, 1, history=True)

    # Action
    if category == "system" or category=="notes":
        adjust_system(content)
    elif category == "song":
        music(content, response)
    elif category == "weather":
        weather(content)
    elif category == "time":
        world_clock(content)
    elif category == "calendar":
        calendar(content)
    # ADD OTHER ACTIONS


    if category == "calendar":
        sys.exit()

    add_assistant_message(response)
    speech(response)

    if category == "system" or category == "song":
        sys.exit()

if __name__ == "__main__":
    while True:
        decision()
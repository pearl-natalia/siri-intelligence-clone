import sys, json
from system.music import music
from system.system import adjust_system
from transcription.speech import speech
from transcription.transcribe import transcribe
from model import model, add_user_message, add_assistant_message, get_history

def get_content(silence_duration=-1):
    if silence_duration != -1:
        transcribe(SILENCE_DURATION=silence_duration)
    else:
        transcribe()
    with open("transcription/transcription.txt", "r") as file:
        content = file.read().strip()
    if content=="":
        return None
    return content

def previous_user_message():
    user_message = None
    for message in reversed(get_history()):
        if message["role"] == "user" and message["content"]!="":
            user_message = message["content"]
            return user_message
    return None

def decision():
    with open('settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)

    # Attempt 1
    content = get_content()
    add_user_message(content)
    
    # No response
    if content is None:
        # Attempt 2
        if previous_user_message() is None:
            speech(f"What can I do for you, {json_data['user_first_name']}?")
        else:
            speech(f"Sorry, I didn't get that. Could you please repeat yourself?")
        content = get_content(3)
        
        if content is None:
            if previous_user_message() is not None
                sys.exit()
            else:
                # Attempt 3
                speech(f"Sorry, I didn't get that. Could you please repeat yourself?")
                content = get_content(3)
                if content is None:
                    sys.exit()

    # Determine the action
    prompt = f"""
            You will take the user's transcription and determine the category that their action belongs in. 
            Here is the input transcription: {content}.
            Output 'communication' if the action involes messages, emails, or facetime calls. 
            Output 'song' if the action involves playing, pausing, opening, etc music. The prompt should include key words like 'play' but don't need to include key words like 'song' for the category to be 'song'.
            Output 'system' if the action can be executed with osa (apple) scripts via the terminal and doesn't involve emails, messages, songs, or facetiming/phone calls). 
            Otherwise, output 'llm' of not 'communication' nor 'system'.
            Only output either 'communication', 'song', 'system', or 'llm' in all lowercase. Do not output any additional text.

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
                    Find me a cookie recipe.
                </INPUT>
                <OUTPUT>
                    system
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
        generate_prompt = f"Generate a friendly 1-2 sentence response to the user's input: {content}. Make sure it's not too long"
    else: # messages, facetime, or email
        generate_prompt = ""
    
    response_prompt =   f""" 
                        You are an expert ai voice assistant. {generate_prompt}. Here is some additional info if needed: {json_string}.
                        Only output the response and no additional text. If the conversation history isn't empty, your job is to continue the conversation.

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
                        """
    response = model(response_prompt, 1, history=True)


    # Action
    if category == "system":
        adjust_system(content)
    elif category == "song":
        music(content, response)
    # elif category == "llm":
    # else: # messages, facetime, or email
    #     generate_prompt = ""

    add_assistant_message(response)
    
    print(response)
    speech(response)

    if category == "system" or category == "song":
        sys.exit() # Stop AI assistant once music plays

if __name__ == "__main__":
    while True:
        decision()
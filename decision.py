import sys, json
from transcription.transcribe import transcribe
from model import model
from system.system import adjust_system
from transcription.speech import speech

def get_content():
    transcribe()
    with open("transcription/transcription.txt", "r") as file:
        content = file.read().strip()
    return content

def decision():
    content = get_content()
    
    # Ask one more time
    if content == "None":
        print("What can I help you with today?")
        content = get_content()
        if content == "None":
            print("Have a good day!")
            return
    
    # Figure out action
    prompt = f"""
            You will take the user's transcription and determine the category that their action belongs in. 
            Here is the input transcription: {content}.
            Output 'communication' if the action involes messages, emails, or facetime calls. 
            Output 'system' if the action can be executed with osa (apple) scripts via the terminal and doesn't involve emails, messages, or facetiming/phone calls). 
            Otherwise, output 'llm' of not 'communication' nor 'system'.
            Only output either 'communication', 'system', or 'llm' in all lowercase. Do not output any additional text.

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
    if category == "system":
        adjust_system(content)
        generate_prompt = f"Generate me a short, concise response to the user's input: {content}"
    elif category == "llm":
        generate_prompt = f"Generate a friendly 1-2 sentence response to the user's input: {content}. Make sure it's not too long"
    else: # messages, facetime, or email
        generate_prompt = ""

    with open('settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)
    
    response_prompt =   f""" 
                            You are an expert ai voice assistant. {generate_prompt}. Here is some additional info if needed: {json_string}.
                            Only output the response and no additional text. 

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
    response = model(response_prompt, 1)
    print(response)
    speech(response)


if __name__ == "__main__":
    decision()

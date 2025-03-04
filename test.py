import sys
from transcription.transcribe import transcribe
from model import model

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
            You are an expert AI voice assistant who executes actions based on user input. 
            You will take the user's transcription and determine the category that action belongs in.
            Output 'communication' if the action involes messages, emails, or facetime calls. 
            Output 'system' if the action involes interaction with the device's system 
            (i.e. adjusting volume, searching something up, essentially anything that can be
            executed with apple scripts via the terminal that doesn't involve emails, messages, or facetiming/phone calls). 
            Output 'llm' if the action involes generating a response to the input with no executable action.
            Output 'none' if the action does not fall under 'communication', 'system', nor 'llm' (i.e. an executable action that can't be done via the terminal). 
            Do not output any additional text.

            Here is the input transcription: {content}.

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
                    none
                </OUTPUT>
             </EXAMPLE>
            """
    
    return model(prompt)

if __name__ == "__main__":
    print('hi')
    # print(decision())
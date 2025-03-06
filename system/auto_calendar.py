import subprocess, sys, os, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../transcription')))
from model import model
from speech import speech
from datetime import datetime

def run_applescript(script):
    result = re.search(r"```applescript\n?(.*?)(```|$)", script.strip(), re.DOTALL)
    if result:
        script = result.group(1).strip()
    process = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True, text=True
    )

    return process.stdout.strip()

def agent(user_request, history, current_info):
    prompt = f"""
                You are a creative AI agent specializing in Apple Calendar interactions. 
                Your primary goal is to fulfill user requests related to their calendar in an intelligent and intuitive way, 
                even when the requests are ambiguous or incomplete. You will leverage your ability to find similarities, 
                infer meaning, and apply common-sense reasoning to provide the best possible user experience.

                **Key Principles:**

                *   **Similarity-Based Matching: When the user mentions a partial or incorrect name, match it to the closest event or attendee. For example, if "lunch with Mike" is mentioned, match it to "Lunch with Michael Davis."
                *   **Iterative Approach:**  You will work iteratively.  First, analyze the user's request and the available information.  If you need more information to fulfill the request, generate an AppleScript to retrieve it.
                    For example, if asked to reschedule a named event today, first output a list of all events today and determine which event name from the list is the most similar, and use the name from the list in the script. Follow a similar approach for attendees of an event, where you can determine which email might be the most similar to the name. Follow approaches like this.
                *   **Data Extraction Focus:** When retrieving calendar information with AppleScript, ensure the script returns a string or structured data (list of dictionaries) containing the requested information. Avoid displaying data in AppleScript alerts or dialogs.
                *   **Context Awareness:**  Carefully consider the `current_info` and `history` to avoid redundant actions and provide relevant responses.  The `history` contains previously generated AppleScripts.
                *   **Date Handling:**  Today's date is {datetime.now().date()} and the current time is {datetime.now().time()}.  Unless the user explicitly specifies a different date, assume the request pertains to today.
                *   **Confirmation and Completion:** Once you have successfully fulfilled the user's request using the available information and the `history`, output *only* the phrase "done generating output".  Do not include any additional text or explanation. Critically evaluate whether the current_info fulfills the user_request.
                *   **Error Handling:** If you encounter an error while generating or executing AppleScript (simulated in this environment), analyze the error and try a different approach.  Don't get stuck in a loop.
                *   **Clarity over Conciseness (in the Thought Process):**  Before generating AppleScript, clearly articulate your reasoning and the specific data you are trying to obtain. Do not articulate the history or current information array.
                *   **Use Common Sense and Real-World Knowledge:** When interpreting the user's request and the `current_info`, rely on common sense and real-world knowledge. Make assumptions to read between the lines.
                        For example, if the user asks if they have a meeting and the only events that day is named 'swimming', that's probably not considered a meeting. Another example: if the user requests to cancel all swimming related activities for the day, first retrieve all event titles for the day, then interpret which titles are swimming related (i.e. pool party) and delete them.
                
                **Input:**

                *   `user_request`:  {user_request}
                *   `current_info`: {current_info}  (This is data you have already gathered from previous AppleScript executions.)
                *   `history`: {history} (This is a list of previously generated AppleScripts)

                **Workflow:**

                1.  **Analyze:** Understand the `user_request` and determine if you have enough information in `current_info` to fulfill it.
                2.  **Plan (If Necessary):** If you need more information:
                    *   Clearly state what information you need.
                    *   Explain *why* you need that information.
                    *   Describe the AppleScript you will generate to retrieve the information. 
                3.  **Generate AppleScript (If Necessary):**  Create the AppleScript code. Ensure it retrieves the data in a usable format (string, list, dictionary). Enclose the code within triple backticks (`````applescript ... `````). Also if setting event at certain time, add 'set time of today to 0' line before setting the time, and add 12 hours to all times that are in PM.
                4.  **Fulfill or Iterate:**
                    *   If you have fulfilled the request, output "done generating output" at the end of your output.
                    *   Otherwise, output the AppleScript.

                Look at the examples, the <OUTPUT></OUTPUT sections are how your output should look.
                <EXAMPLE>
                    <INPUT>
                        User request: What does my day look like?
                        Gathered info: []
                        History: []
                    </INPUT>

                    <OUTPUT>
                        Okay, I need to find the events happening today.
                    
                        ```
                        applescript
                        tell application "Calendar"
                            tell calendar "Calendar"
                                    set todayStart to (current date) - (time of (current date))
                                    set todayEnd to todayStart + (1 * days)
                                    set todayEvents to (every event whose start date is greater than or equal to todayStart and start date is less than todayEnd)
                                    if (count of todayEvents) > 0 then
                                        set eventDetails to {{}}
                                        repeat with anEvent in todayEvents
                                            set eventName to summary of anEvent
                                            set startTime to start date of anEvent
                                            set end of eventDetails to {{name:eventName, start:startTime}}
                                        end repeat
                                        return eventDetails
                                    else
                                        return "No events found for today."
                                end if
                            end tell
                        end tell
                        ```
                    </OUTPUT>
                <\EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        User request: Who is in my meeting today?
                        Gathered info: []
                        History: []
                    </INPUT>

                    <OUTPUT>
                        Okay, I need to find the invitees in the meeting today.
                    
                        ```
                        applescript
                        tell application \"Calendar\" tell calendar \"Calendar\" set todayStart to (current date) - (time of (current date))
                        set todayEnd to todayStart + (1 * days) set todayEvents to (every event whose start date is greater than or equal to todayStart and start date is less than todayEnd)
                        if (count of todayEvents) > 0 then set eventDetails to {{}} repeat with anEvent in todayEvents set eventName to summary of anEvent
                        set startTime to start date of anEvent try set theInvitees to attendees of anEvent set inviteeList to {{}}
                        repeat with i from 1 to the count of theInvitees set end of inviteeList to (email of item i of theInvitees)
                        end repeat return {{name:eventName, start:startTime, invitees:inviteeList}} on error
                        return {{name:eventName, start:startTime, invitees:\"No invitees found\"}} end try end repeat
                        else return \"No events found for today.\" end if end tell end tell
                        ```
                    </OUTPUT>
                <\EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        User request: What does my day look like?
                        Gathered info: ['name:Meeting, start:date Wednesday, March 5, 2025 at 9:00:00 PM']
                        History: [<apple script>]
                    </INPUT>
                    <OUTPUT>
                        done generating output
                    </OUTPUT>
                <\EXAMPLE>


            Here is the input:

            User request: {user_request}
            Gathered info: {current_info}
            """

    response = model(prompt, 1.5)
    return response

def agent_reply(user_request, llm_responses, information):
    prompt =    f"""
                You are an AI assistant who was given a request related th Apple Calendar by the user and have already performed the action. 
                Generate a very concise, friendly response based on the user request and the outcome. Only output the response as it will directly be transcribed.
                Here is the user's request: {user_request}
                For context, here is the information gathered: {information}.
                Here are the previous assistant responses: {llm_responses}.
                """
    response = model(prompt, 1.5)
    speech(response)


def calendar(user_request):
    llm_responses = []
    information = []
    counter = 7

    while True:
        reply = agent(user_request, llm_responses, information).strip()
        if reply.endswith("done generating output"):
            result = run_applescript(reply).strip()
            information.append(result)
            break
        llm_responses.append(reply)
        result = run_applescript(reply).strip()
        if result != None and result != "":
            information.append(result)
        counter -=1
        if counter == 0:
            break
    
    # LLM Response
    if len(llm_responses) == 0: 
        llm_responses = []
    elif len(llm_responses) == 1: 
        llm_responses = llm_responses[0]
    else:
        llm_responses = llm_responses.slice(-2)
    
    agent_reply(user_request, llm_responses, information)
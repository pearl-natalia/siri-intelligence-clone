### Overview
Swift is an AI assistant for MacBooks, inspired by what Siri could become with Apple Intelligence by 2026. It processes voice commands by breaking them down into executable AppleScript actions via AI agents.

<p align="center">
  <img width="90%" alt="alt-text" src="https://github.com/user-attachments/assets/cb4f2774-fccf-499e-a419-fd3f3b623096" />
</p>

### INPUT
The voice assistant will listen for input audio until a threshold of silence, giberish (umms, ands, etc) or background noise is met. Whisper will then output the transcription into a .txt which will serve as the initial input for the voice assistant. 

Using few-shot prompting, Gemini determines the category of the action (refer to diagram). This is crucial to ensure specific APIs are only provided to the agent when needed. 

### EXECUTION
Then, the agent uses chain-of-thought reasoning to break down the request into smaller steps to understand how to achieve it with executable actions.

#### EXAMPLE 
- Input: "Cancel my meeting tmrw"
- Chain-of-thought"
    1. Find all events from Calendar happening tomorrow 
    2. Determine which of these events can be a meeting based on the event name
        - If only 1 "meeting" event, cancel it
        - If more than 1 "meeting" event, request more details from user to understand which meeting to cancel
        - If no "meeting", let user know there's no meeting
    
    3. Only 1 "meeting" event was found. Generate an AppleScript to cancel this meeting.
    4. Received an error response to executing the script. Generate a different script.
    5. Successful response. Exiting...

#### MUSIC
For song related requests, the agent as access to a spotify API to convert song/playlist/album names into a URI. This URI is used in an AppleScript to play that song. The agent can also suggest songs, play top tracks, etc.

#### WEATHER
The agent combines live location info (core location) with a weather API to get up-to-date weather-related information.

#### COMMUNICATION
For all communication-related tasks, the agent utilizes contact information to identify the intended recipient. By outputting your contacts list and performing a phonetic similarity search, Swift can accurately determine which contact you're referencing, even if the transcription differs from the actual spelling. This approach also enables you to send emails by simply mentioning a name rather than verbally stating the full email address. 

#### iMessage
o generate iMessage responses that match the user's style, the last few iMessages are analyzed to capture the tone, structure (e.g., capitalization), formality, and context of the conversation. A SQL database also tracks the top N most frequently used words and phrases by the user, which reflect their personality and communication style (such as preferred expressions or specific spelling). These insights are then used to make future responses align more closely with the user's way of communicating.

#### LLM
This category handles conversational and inquiry-based requests. Since it's conversation-driven, the LLM will continue engaging with the user until they close the voice assistant. The interaction is stored locally for faster retrieval and provided as history to Gemini, ensuring detailed long-term memory throughout the conversation.

#### RAG (IN PROGRESS)
These stored interactions in SQL are intended to be converted into a vector database, enabling Retrieval-Augmented Generation (RAG) to fetch relevant context for future interactions. For example, if a user asks, "What reminders did I set earlier today?" or "Can you play the same playlist I requested this morning?", the system can accurately retrieve and reference past requests.

### OUTPUT
At the end of the conversation, the local history is stored in a global SQL database, enabling persistent memory through RAG for future interactions. A final response is then delivered using PlayAI for a natural, human-like voice before the system automatically exits.

### USE CASES

<p align="center">
  <img width="90%" alt="alt-text" src="https://github.com/user-attachments/assets/19abf663-f51e-49ff-b521-51fd42ddc8d4" />
</p>

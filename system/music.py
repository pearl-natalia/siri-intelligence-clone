import spotipy, sys, subprocess, os, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials
from model import model

def get_spotify_id(query, search_type):
    load_dotenv()
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("API key is missing. Make sure it's in your .env file.")
    client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    
    results = sp.search(q=query, limit=1, type=search_type)
    if results[search_type + 's']['items']:
        item = results[search_type + 's']['items'][0]
        return item['id']  
    return None

def get_music_action(dialogue, llm_response):
    prompt = f"""
                You are an AI assistant.
                Extract the song name, playlist, album, or artist from the user's dialogue based on what they are requesting. 
                Extract song name if requesting to play a song. Extract playlist/album if requesting to play from a specific playlist/album. 
                Extract artist if requesting to play from a specific artist. If neither song name, playlist, album, nor artist is mentioned, return 'not enough info, not enough info'. 
                You may also research names if needed. Example: if asked to play the weeknd's newest album, research what that is, and then return <newest album name>, album.
                If the user asked the AI assistant to pick the music, then extract the info from the AI's response. 
                Output in the following format with no additional text:
                <OUTPUT FORMAT>
                    extracted info, <track/playlist/album/artist>
                </OUTPUT FORMAT>
                
                <EXAMPLE>
                    <INPUT> 
                        User: Play my favourite song shape of you by ed sheeran.
                        AI: Now playing shape of you by Ed Sheeran.
                    </INPUT>
                    <OUTPUT>
                        Shape of You, track
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play from my gym playlist.
                        AI: Now playing your gym playlist.
                    </INPUT>
                    <OUTPUT>
                        gym, playlist
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play Adele's top tacks.
                        AI: Now playing Adele's top tracks.
                    </INPUT>
                    <OUTPUT>
                        Adele, artist
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play the Weeknd's newest album.
                        AI: Now playing the weeknd.
                    </INPUT>
                    <OUTPUT>
                        Hurry Up Tomorrow, album
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play a song.
                        AI: What song would you like to play?
                    </INPUT>
                    <OUTPUT>
                        not enough info, not enough info
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play music.
                        AI: Now playing music on spotify.
                    </INPUT>
                    <OUTPUT>
                        not enough info, not enough info
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        User: Play a happy song.
                        AI: Now playing "The Elements" by Tom Lehrer on Spotify!
                    </INPUT>
                    <OUTPUT>
                        The Elements, track
                    </OUTPUT>
                </EXAMPLE>

                Here is the input: 
                <INPUT>
                    User: {dialogue}
                    AI: {llm_response}
                </INPUT>
            """

    song_info, action_type = model(prompt, 1).rsplit(',', 1)
    song_info = song_info.strip()
    action_type = action_type.strip()
    return song_info, action_type

def play_music(dialogue, llm_response):
    song_info, action_type = get_music_action(dialogue, llm_response)
    play_music_errors = True

    if song_info != "not enough info" and action_type != "not enough info":
        spotify_id = get_spotify_id(song_info, action_type)
        if spotify_id is not None:
            apple_script = f'tell application "Spotify" to play {action_type} "spotify:{action_type}:{spotify_id}"'
            subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)
            play_music_errors = False
    
    # Can't play song
    if play_music_errors:
        music_system(dialogue)

def music_system(dialogue):
    with open('settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)
    prompt =    f"""
                You are an assistant skilled in generating AppleScript (OSA) scripts for automating music related tasks on macOS. 
                You will be executing these tasks with Spotify. Based on the user's needs, generate the AppleScript code that performs the following task(s): {dialogue}.
                If increasing/decreasing any setting, do it by 2x (i.e. increase volume by 20 instead of 10). 
                Only output the scripts, no additional text. Use the examples to determine how the output should be formatted.
                If the task can't be achieved via an apple script, output "cannot generate script". 
                Use the following settings to adjust the scripts to the user's preferences (i.e. default browser): 
                
                <USER SETTINGS>
                    {json_string}
                </USER SETTINGS>

                <EXAMPLE>
                    <INPUT>
                        Pause my music
                    </INPUT>
                    <OUTPUT>
                        tell application "Spotify" to pause
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Play the previous song
                    </INPUT>
                    <OUTPUT>
                        tell application "Spotify" previous track previous track end tell
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Go back a song
                    </INPUT>
                    <OUTPUT>
                        tell application "Spotify" previous track previous track end tell
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Play my music louder.
                    </INPUT>
                    <OUTPUT>
                        set volume output volume (output volume of (get volume settings) + 10)" && osascript -e "tell application \"System Events\" to key code 144
                    </OUTPUT>
               
                </EXAMPLE>
                    <INPUT>
                        Play a song.
                    </INPUT>
                    <OUTPUT>
                        cannot generate script
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Charge my macbook.
                    </INPUT>
                    <OUTPUT>
                        cannot generate script
                    </OUTPUT>
                </EXAMPLE>
                """
    apple_script = model(prompt, 1.5)
    subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)

def music(dialogue, llm_response):
    prompt = f"""
                Your job is to classify the user's request into 2 categories, 'play' and 'other'. 
                Output 'play' if the task involves playing music (song, album, artist, playlist, etc). Otherwise, output 'other'.
                Only output either 'play' or 'other', no additional text.
                
            
                <EXAMPLE>
                    <INPUT> 
                        Play the Weeknd's top tracks.
                    </INPUT>
                    <OUTPUT>
                        play
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT> 
                        Pause my music.
                    </INPUT>
                    <OUTPUT>
                        other
                    </OUTPUT>
                </EXAMPLE>

                Here is the user's request: {dialogue}
            """
    
    category = model(prompt, 1.5).strip()
    if category == "play":
        play_music(dialogue, llm_response)
    else:
        music_system(dialogue)
import subprocess, re, os, sys, json, time, platform
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../transcription')))
from speech import speech
from model import model
from datetime import datetime
from pyicloud import PyiCloudService
from dotenv import load_dotenv

import os
import platform
from dotenv import load_dotenv
from pyicloud import PyiCloudService

def get_location():
    load_dotenv()
    iCloud_user = os.getenv("ICLOUD_USER")
    iCloud_pass = os.getenv("ICLOUD_PASSWORD")
    api = PyiCloudService(iCloud_user, iCloud_pass)
    device_name = platform.node()  # Current macbook's name
    
    device_name = "Pearl's Macbook Air" # TMP; REMOVE
    chosen_device = None
    for device in api.devices:
        if device.get('name') == device_name:
            return f"[{device.location()['latitude']}, {device.location()['longitude']}]"
    return None    


def adjust_system(task):
    with open('settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)
    current_datetime = datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
    

    prompt = f"""
            You are an assistant skilled in generating AppleScript (OSA) scripts for automating tasks on macOS.
            Based on the user's needs, generate the AppleScript code that performs the following task(s): {task}.
            You will be creative with how you achieve more complex tasks and break them down. 
            Only output the scripts, no additional text. Use the examples to determine how the output should be formatted.
            If the task can't be achieved via an apple script, output "cannot generate script". 
            If increasing/decreasing any setting, do it by 2x (i.e. increase volume by 20 instead of 10).
            Use the following settings to adjust the scripts to the user's preferences (i.e. default browser): 
            
            <USER SETTINGS>
                {json_string}
            </USER SETTINGS>

            <EXAMPLE>
                <INPUT>
                Increase the volume.
                </INPUT>
                <OUTPUT>
                set currentVolume to output volume of (get volume settings)
                set newVolume to currentVolume + 20
                if newVolume > 100 then
                    set newVolume to 100 
                end if
                set volume output volume newVolume
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT>
                    Decrease brightness.
                </INPUT>
                <OUTPUT>
                    tell application \"System Events\" to key code 144" -e "tell application \"System Events\" to key code 144
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT>
                    Increase volume and decrease brightness.
                </INPUT>
                <OUTPUT>
                    set volume output volume (output volume of (get volume settings) + 10)" && osascript -e "tell application \"System Events\" to key code 144
                </OUTPUT>
            </EXAMPLE>

            <EXAMPLE>
                <INPUT>
                    Close all apps except Chrome, Safari, and VS Code.
                </INPUT>
                <OUTPUT>
                    set keepApps to {{"Google Chrome", "Safari", "Visual Studio Code"}}
                    tell application "System Events"
                        set appList to name of (processes where background only is false)
                    end tell
                    repeat with appName in appList
                        if appName is not in keepApps then
                            try
                                do shell script "killall '" & appName & "'"
                            end try
                        end if
                    end repeat
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

            Side note: today's date is {current_datetime}. Current location coorindates are: {get_location()}.
            """
    apple_script = model(prompt, 1)
    print(apple_script)
    subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)


def world_clock(dialogue):
    prompt =    f"""
                Your job is to determine the city the user is inquiring about, given the user input. 
                If a country/state/province is specified, return the Capital city of it. If a description of a city is given, then return that city.
                If it seems user is asking about time in their current location, return 'current'.  If the details are too borad to specify a city/capital city, return 'no city'. 
                Only return the specified output format with no additional text. 

                <EXAMPLE>
                    <INPUT>
                        What time is it in Canada.
                    </INPUT>
                    <OUTPUT>
                        Ottawa
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        What time is it right now.
                    </INPUT>
                    <OUTPUT>
                        current
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        What time is it in North America.
                    </INPUT>
                    <OUTPUT>
                        no city
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        What time is it at the eiffel tower.
                    </INPUT>
                    <OUTPUT>
                        Paris
                    </OUTPUT>
                </EXAMPLE>

                Here is the user input: {dialogue}
                """
    city = model(prompt, 1)

    if city == "current":
        date = f"Here is the current date: {datetime.now().date()} and time: {datetime.now().time()}"
    elif city == "no city":
        speech("Sorry, I don't have that information")
        sys.exit()
    else:
        prompt = f"""
                    Generate an osascript to get the date and time of the following city: {city}. 
                    Only outout the apple script string, no additional text.

                    <EXAMPLE>
                        <INPUT>
                            Dubai
                        </INPUT>
                        <OUTPUT>
                            return do shell script "TZ=Asia/Dubai date"
                        </OUTPUT>
                    </EXAMPLE>
                """
        apple_script = model(prompt, 1.5)
        date = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True).stdout.strip()
    
    prompt =    f"""
                Generate a short and concise respond to the user's question: {dialogue} 
                using the following information: {date}. Here is the city: {city}. Reformat the time in AM/PM format.
                If the user asks for the time, you don't need to specify the date.
                Include the city and country unless user is asking for time in their current location.

                <EXAMPLE>
                    <INPUT>
                        Time in dubai.
                    </INPUT>
                    <OUTPUT>
                        It's currently 5:12 am in Dubai, UAE.
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        What's the time right now?
                    </INPUT>
                    <OUTPUT>
                        It's currently 9:30 pm.
                    </OUTPUT>
                </EXAMPLE>

                <EXAMPLE>
                    <INPUT>
                        Time in France.
                    </INPUT>
                    <OUTPUT>
                        It's currently 1:03 am in Paris, France.
                    </OUTPUT>
                </EXAMPLE>
                """
    response = model(prompt, 1.5)
    speech(response)
    sys.exit()
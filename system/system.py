import subprocess, re, os, sys, json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model import model
from datetime import datetime

def adjust_system(task):
    with open('../settings.json', 'r') as file:
        json_data = json.load(file)
    json_string = json.dumps(json_data)
    current_datetime = datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")

    prompt = f"""
            You are an assistant skilled in generating AppleScript (OSA) scripts for automating tasks on macOS.
            Based on the user's needs, generate the AppleScript code that performs a following task(s): {task}.
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
                    Charge my macbook.
                    </INPUT>
                    <OUTPUT>
                    cannot generate script
                    </OUTPUT>
                </EXAMPLE>

                Side note: today's date is {current_datetime}.
            """
    apple_script =  model(prompt, 2)
    subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)


if __name__ == "__main__":
    input = "set a detailed reminder to buy apples for tmrw at 9 am"
    adjust_system(input)


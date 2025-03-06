
import requests, os, sys, json
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'transcription')))
from dotenv import load_dotenv
from speech import speech
from model import model

def weather(dialogue):
    # API
    load_dotenv()
    api_key = os.getenv("WEATHER_API")
    if not api_key:
        raise ValueError("API key is missing. Please check your .env file.")
    
    prompt =    f"""
                    Your job is to determine the city the user is inquiring about, given the user input. 
                    If a country/state/province is specified, return the Capital city of it. 
                    If anything else is specified (i.e. a contient), then return 'no city'. 
                    You will also determine if the user is asking for weather now or in the future. If a future date is specified (not within next 24 hours), it's 'forecast'. Otherwise, it's 'current'. If 'no city', then write 'no time'.
                    Only return the specified output format with no additional text. 

                    <OUTPUT FORMAT>
                        city, <forecast/current/>
                    </OUTOUT FORMAT>

                    <EXAMPLE>
                        <INPUT>
                            What's the weather like in Toronto.
                        </INPUT>
                        <OUTPUT>
                            Toronto, current
                        </OUTPUT>
                    </EXAMPLE>

                    <EXAMPLE>
                        <INPUT>
                            How cold is it in Canada in 1 hour.
                        </INPUT>
                        <OUTPUT>
                            Ottawa, current
                        </OUTPUT>
                    </EXAMPLE>
                        <INPUT>
                            How cold is it in California tomorrow.
                        </INPUT>
                        <OUTPUT>
                            Sacramento, forecast
                        </OUTPUT>
                    </EXAMPLE>

                    </EXAMPLE>
                        <INPUT>
                            Weather in north america?
                        </INPUT>
                        <OUTPUT>
                            no city, no time
                        </OUTPUT>
                    </EXAMPLE>

                    Here is the user input: {dialogue}
                """
    
    city, time = model(prompt, 1).rsplit(',', 1)
    city = city.strip()
    time = time.strip()

    if city == "no city" or time == "no time":
        speech("Unfortunately, I don't have that information at this time.")
        sys.exit()

    url = f"https://api.weatherapi.com/v1/{time}.json?key={api_key}&q={city}"
    data = requests.get(url).json()
    current_datetime = datetime.now()
    curr_date = current_datetime.date()
    curr_time = current_datetime.time()

    prompt =    f"""
                    You are an AI assistant who is in charge of giving the user weather info based on their request: {dialogue}. 
                    You will parse the given json to extract the requested info and generate a concise 1 sentence message 
                    to answer the user's weather request. Here is the json: {data}. Don't need to mention country if user only mentions city.

                    <EXAMPLE OUTPUT> It's currently 3 degrees celcius. </EXAMPLE OUTPUT>
                """
    
    speech(model(prompt, 2))
    sys.exit()
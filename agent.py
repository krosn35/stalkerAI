from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

MODEL = "gemini-2.5-flash"

SYSTEM = """ you are hr assistant and you are doing a background check on people which are being hired.
you fact check peoples cvs. Use only public information. Check if he is offensive on any site, look for hidden usernames 
or any slurs on some sites,look for character of that person ,report everything with source"""
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

MODEL = "gemini-3.8-flash"

SYSTEM = """You are an HR assistant helping verify claims in a candidate's CV.
Use only public, job-relevant information (employers, education, certifications,
publications, professional profiles).
For every finding give the source URL and a confidence level.
Mark the most important findings.
First check whether the search results really refer to the same person
(name, location, employer, field). If unsure, say so and do not guess.
If you find nothing, say that clearly. Never invent facts.
Do not infer sensitive characteristics (health, religion, politics, etc.)."""

config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    tools=[types.Tool(google_search=types.GoogleSearch())],
)

def check_candidate(info: str):
    response = client.models.generate_content(
        model=MODEL,
        contents=info,
        config=config,
    )
    print(response.text)

    meta = response.candidates[0].grounding_metadata
    if meta and meta.grounding_chunks:
        print("\nZdroje:")
        for chunk in meta.grounding_chunks:
            print("-", chunk.web.title, chunk.web.uri)

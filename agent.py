import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools import PersonReport   # schéma z tool.py

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

search_config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    tools=[types.Tool(google_search=types.GoogleSearch())],
)

json_config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    response_mime_type="application/json",
    response_schema=PersonReport,
)

def search_step(info: str) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=info,
        config=search_config,
    )
    text = response.text or ""

    try:
        meta = response.candidates[0].grounding_metadata
        if meta and meta.grounding_chunks:
            text += "\n\nSources:\n" + "\n".join(
                f"- {c.web.title}: {c.web.uri}" for c in meta.grounding_chunks if c.web
            )
    except (IndexError, AttributeError):
        pass

    return text

def json_step(notes: str) -> PersonReport:
    response = client.models.generate_content(
        model=MODEL,
        contents=(
            "Convert the notes below into the structured report. "
            "Use only information from the notes, do not invent anything. "
            "If something is missing, leave it empty.\n\n" + notes
        ),
        config=json_config,
    )
    return response.parsed

def check_candidate(info: str) -> PersonReport:
    notes = search_step(info)
    return json_step(notes)

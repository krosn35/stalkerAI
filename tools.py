from pydantic import BaseModel

class Source(BaseModel):
    title: str
    url: str

class Position(BaseModel):
    company: str
    role: str
    period: str

class PersonReport(BaseModel):
    full_name: str
    summary: str
    confidence: str
    career: list[Position]
    notable_work: list[str]
    public_appearances: list[Source]
    interview_questions: list[str]
    sources: list[Source]

import re
import asyncio
from pydantic import BaseModel

import api


# ---------- Schéma výstupu ----------

class Source(BaseModel):
    title: str
    url: str

class Position(BaseModel):
    company: str
    role: str
    period: str | None = None

class PersonReport(BaseModel):
    full_name: str
    summary: str
    confidence: str
    career: list[Position]
    notable_work: list[str]
    public_appearances: list[Source]
    interview_questions: list[str]
    sources: list[Source]


# ---------- Tool pro Instagram ----------

def get_instagram_profile(username: str) -> dict:
    """Načte veřejné informace z Instagram profilu, jehož uživatelské jméno je známé.
    Použij ji jen tehdy, když uživatel uvedl konkrétní Instagram username.
    Nikdy si username nehádej a nehledej profil podle jména osoby.

    Args:
        username: Instagram uživatelské jméno (s @ nebo bez).
    """
    username = username.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        return {"error": "Neplatné uživatelské jméno."}

    try:
        api.init()   # načte APIFY_TOKEN z prostředí
        profile = asyncio.run(api.scrape_ig_profile(username))
    except Exception as e:
        return {"error": f"Scraper selhal: {e}"}

    if not profile:
        return {"error": "Profil nenalezen nebo scraper nic nevrátil."}

    # Vracíme jen základní veřejné údaje relevantní pro ověření identity a profese.
    return {
        "username": profile.get("username"),
        "full_name": profile.get("fullName"),
        "biography": profile.get("biography"),
        "external_url": profile.get("externalUrl"),
        "is_verified": profile.get("verified"),
        "is_private": profile.get("private"),
        "is_business_account": profile.get("isBusinessAccount"),
        "business_category": profile.get("businessCategoryName"),
        "followers": profile.get("followersCount"),
        "posts_count": profile.get("postsCount"),
        "profile_url": f"https://www.instagram.com/{username}/",
    }
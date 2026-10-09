import os
from collections.abc import Mapping
import unicodedata
from difflib import SequenceMatcher
from apify_client import ApifyClientAsync

TOKEN = None

def _run_dataset_id(run, platform: str) -> str:
    """Support both dictionary responses and typed Apify Run responses."""
    if isinstance(run, Mapping):
        status = run.get("status")
        dataset_id = run.get("defaultDatasetId")
    else:
        status = getattr(run, "status", None)
        dataset_id = getattr(run, "default_dataset_id", None)
    status = getattr(status, "value", status)
    if status != "SUCCEEDED":
        raise RuntimeError(f"{platform} actor did not complete successfully (status={status})")
    if not dataset_id:
        raise RuntimeError(f"{platform} actor returned no dataset ID")
    return dataset_id


def _profile_fields(profile) -> dict[str, str]:
    # Keep legacy name-only callers working, but accept the full form object.
    if isinstance(profile, str):
        profile = {"name": profile}
    fields = {}
    for field in ("name", "school", "city"):
        value = profile.get(field, "") if isinstance(profile, Mapping) else getattr(profile, field, "")
        if value is None and field != "name":
            value = ""
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        fields[field] = value.strip()
    if not _normalize_name(fields["name"]):
        raise ValueError("name must contain letters or numbers")
    return fields


def _context_match_score(fields: dict[str, str], candidate: dict) -> float:
    def text(value):
        if isinstance(value, Mapping):
            return " ".join(text(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return " ".join(text(item) for item in value)
        return value if isinstance(value, str) else ""

    evidence = _normalize_name(text(candidate))
    scores = []
    for field in ("school", "city"):
        query = _normalize_name(fields[field])
        field_evidence = evidence
        if field == "city":
            query = " ".join("prague" if token == "praha" else token for token in query.split())
            field_evidence = " ".join("prague" if token == "praha" else token for token in evidence.split())
        if query:
            query_tokens = set(query.split())
            scores.append(len(query_tokens & set(field_evidence.split())) / len(query_tokens))
    return sum(scores) / len(scores) if scores else 0.0

def init():
    global TOKEN
    TOKEN = os.getenv("APIFY_TOKEN")

def _normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return " ".join("".join(
        char if char.isalnum() else " "
        for char in decomposed if not unicodedata.combining(char)
    ).split())


def _name_match_score(query: str, candidate: str) -> tuple:
    query = _normalize_name(query)
    candidate = _normalize_name(candidate)
    if not candidate:
        return (0, 0, 0, 0)
    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    overlap = len(query_tokens & candidate_tokens)
    # Exact names win, followed by all query words (including reordered names
    # or profiles with middle names), then partial and fuzzy matches.
    return (
        int(query == candidate),
        int(query_tokens <= candidate_tokens),
        2 * overlap / (len(query_tokens) + len(candidate_tokens)),
        SequenceMatcher(None, query, candidate).ratio(),
    )


async def search_linkedin_accounts(name: str, max_results: int = 10) -> list[dict[str, str]]:
    """Return possible matches as JSON-serializable name/linkedin_url/info objects.

    Matches are search candidates, not verified identities. info contains the
    profile headline and location when available.
    Results are ranked by name similarity, ignoring case and accents;
    LinkedIn's original order is preserved for equally ranked matches.
    """
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if max_results < 1:
        raise ValueError("max_results must be positive")

    apify_client = ApifyClientAsync(TOKEN)
    call_result = await apify_client.actor("harvestapi/linkedin-profile-search").call(
        run_input={
            "searchQuery": name,
            "profileScraperMode": "Short",
            "maxItems": max_results,
        }
    )
    # if call_result is None or call_result.get("status") != "SUCCEEDED":
    #     raise RuntimeError("LinkedIn search actor did not complete successfully")

    accounts = []
    seen_urls = set()
    dataset = apify_client.dataset(call_result.default_dataset_id)
    async for profile in dataset.iterate_items():
        url = profile.get("linkedinUrl")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        full_name = " ".join(
            part for part in (profile.get("firstName"), profile.get("lastName")) if part
        ).strip()
        location = profile.get("location") or ""
        if isinstance(location, dict):
            location = location.get("linkedinText") or ""
        headline = profile.get("headline") or profile.get("position") or ""
        accounts.append({
            "name": full_name or profile.get("name") or "",
            "linkedin_url": url,
            "info": " | ".join(part for part in (headline, location) if part),
        })
        if len(accounts) >= max_results:
            break
    accounts.sort(key=lambda account: _name_match_score(name, account["name"]), reverse=True)
    return accounts

async def search_instagram_accounts(name: str, max_results: int = 10) -> list[dict[str, str]]:
    """Return name/username/instagram_url/info objects, best names first.

    username excludes the @ prefix; info contains the bio when available. Matches are candidates,
    not verified identities. Live search tries name and username variants and
    ranks a larger candidate pool by name/username similarity, never popularity.
    """
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if not 1 <= max_results <= 250:
        raise ValueError("max_results must be between 1 and 250")
    if "," in name:
        raise ValueError("name must not contain commas (Instagram treats them as separate searches)")

    normalized = _normalize_name(name)
    tokens = normalized.split()
    # The actor rejects punctuation such as dots, hyphens and apostrophes in
    # search terms. Preserve accents in the name query but replace punctuation.
    search_name = " ".join("".join(
        char if char.isalnum() or char.isspace() else " " for char in name
    ).split())
    queries = list(dict.fromkeys(filter(None, [
        search_name, normalized, "".join(tokens), "_".join(tokens),
    ])))
    if not queries:
        raise ValueError("name must contain letters or numbers")
    # Retrieve more candidates than we return so upstream ordering cannot
    # exclude a strong name match simply because it falls outside the top ten.
    search_limit = min(250, max(50, max_results * 5))
    apify_client = ApifyClientAsync(TOKEN)
    call_result = await apify_client.actor("apify/instagram-search-scraper").call(
        run_input={
            "search": ",".join(queries),
            "searchType": "user",
            "searchLimit": search_limit,
            "liveSearch": True,
            "enhanceUserSearchWithFacebookPage": False,
        }
    )
    # if call_result is None or call_result.get("status") != "SUCCEEDED":
    #     raise RuntimeError("Instagram search actor did not complete successfully")

    accounts = []
    seen_urls = set()
    dataset = apify_client.dataset(call_result.default_dataset_id)
    async for profile in dataset.iterate_items():
        username = (profile.get("username") or "").strip().lstrip("@")
        url = f"https://www.instagram.com/{username}/" if username else profile.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        accounts.append({
            "name": profile.get("fullName") or profile.get("full_name") or username,
            "username": username,
            "instagram_url": url,
            "info": profile.get("biography") or "",
        })
    def match_score(account):
        display_score = _name_match_score(name, account["name"])
        username_score = _name_match_score(name, account["username"])
        compact_query = normalized.replace(" ", "")
        compact_username = _normalize_name(account["username"]).replace(" ", "")
        exact_username = bool(compact_query) and compact_query == compact_username
        return (
            display_score[0],
            int(exact_username),
            max(display_score[1], username_score[1]),
            max(display_score[2], username_score[2]),
            max(display_score[3], username_score[3]),
        )

    accounts.sort(key=match_score, reverse=True)
    return accounts[:max_results]


async def scrape_ig_profile(username):
    apify_client = ApifyClientAsync(TOKEN)

    actor_client = apify_client.actor("apify/instagram-profile-scraper")
    call_result = await actor_client.call(run_input={
        "usernames": [username],
        "includeAboutSection": False
    })

    if call_result is None:
        return None

    dataset_client = apify_client.dataset(call_result["defaultDatasetId"])
    list_items_result = await dataset_client.list_items()

    profile = list_items_result.items[0]

    return profile

async def scrape_linkedin_profile(url):
    apify_client = ApifyClientAsync(TOKEN)

    actor_client = apify_client.actor("harvestapi/linkedin-profile-scraper")
    call_result = await actor_client.call(run_input={
        "profileScraperMode": "Profile details no email ($4 per 1k)",
        "queries": [url]
    })

    if call_result is None:
        return None

    dataset_client = apify_client.dataset(call_result["defaultDatasetId"])
    list_items_result = await dataset_client.list_items()

    profile = list_items_result.items[0]

    return profile

if __name__ == "__main__":
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    init()

    result = asyncio.run(search_linkedin_accounts(name="Pavel Vrana", max_results=10))

    print(result)

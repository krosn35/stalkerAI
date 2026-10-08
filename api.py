import os
from apify_client import ApifyClientAsync

TOKEN = None

def init():
    global TOKEN
    TOKEN = os.getenv("APIFY_TOKEN")

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

    result = asyncio.run(scrape_linkedin_profile("https://cz.linkedin.com/in/pavel-vr%C3%A1na-577336297"))

    print(result)
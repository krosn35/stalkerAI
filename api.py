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

if __name__ == "__main__":
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    init()

    result = asyncio.run(scrape_ig_profile("sspsprague"))

    print(result)
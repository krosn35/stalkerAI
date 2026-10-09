# StalkerAI

Find LinkedIn and Instagram profile candidates from one desktop app.

- Search by name, with optional school and city hints.
- Rank results using similarity to user input.
- Export search results as JSON.

## Video

[![Watch on YouTube](https://img.youtube.com/vi/36GPe3UtTY4/hqdefault.jpg)](https://youtu.be/36GPe3UtTY4)

## Run

Create a `.env` file in the project root:

```dotenv
APIFY_TOKEN=your_apify_api_key
TEST=ok!
```

`TEST` is the startup diagnostic text. Then run:

```bash
python3 main.py
```

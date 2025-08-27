import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [
    int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()
]

USERS_FILE = "data/users.json"
QUERIES_FILE = "data/queries.json"
CACHED_ADS_FILE = "data/cached_ads.json"

# You can adjust the delay between queries in seconds, if you need.
DELAY_BETWEEN_QUERIES = int(os.getenv("DELAY_BETWEEN_QUERIES", 5))
DELAY_MAIN_LOOP = int(
    os.getenv("DELAY_MAIN_LOOP", 60)
)  # seconds before the next parsing attempt

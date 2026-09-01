import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def load_config():
    return {
        "PREFIX": os.getenv("PREFIX", "!"),
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN", ""),
        "MONGODB_URI": os.getenv("MONGODB_URI", ""),
        "DB_NAME": os.getenv("DB_NAME", "bise_result_bot"),
        # Keep this configurable because BISE can change its result endpoint.
        "OFFICIAL_RESULT_URL": os.getenv(
            "OFFICIAL_RESULT_URL",
            "https://www.bisegrw.edu.pk/downloads/affiliations/exam-and-results/prev-years-result.html"
        ),
        "RESULT_CHANNEL_ID": int(os.getenv("RESULT_CHANNEL_ID", "0")),
        "MENTION_ROLE_ID": int(os.getenv("MENTION_ROLE_ID", "0")),
        "FALLBACK_RESULT_URL": os.getenv("FALLBACK_RESULT_URL", ""),
        "HTTP_TIMEOUT": float(os.getenv("HTTP_TIMEOUT", "20")),
        "PER_REQUEST_DELAY": float(os.getenv("PER_REQUEST_DELAY", "2")),
        "AUTO_CHECK_ENABLED": os.getenv("AUTO_CHECK_ENABLED", "true").lower() == "true",
    }

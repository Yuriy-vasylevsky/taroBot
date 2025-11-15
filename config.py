import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not provided!")
if not OPENAI_API_KEY:
    print("❌ ERROR: OPENAI_API_KEY not provided!")

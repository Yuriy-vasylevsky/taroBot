# import os
# from dotenv import load_dotenv

# load_dotenv()

# BOT_TOKEN = os.getenv("BOT_TOKEN")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# ADMIN_ID = os.getenv("ADMIN_ID")


# if not BOT_TOKEN:
#     print("❌ ERROR: BOT_TOKEN not provided!")
# if not OPENAI_API_KEY:
#     print("❌ ERROR: OPENAI_API_KEY not provided!")


import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === ВИПРАВЛЕННЯ ADMIN_ID ===
raw_admin = os.getenv("ADMIN_ID")
ADMIN_ID = int(raw_admin) if raw_admin and raw_admin.strip().isdigit() else None

print(f"✅ ADMIN_ID завантажено: {ADMIN_ID} (тип: {type(ADMIN_ID)})")
print(f"   BOT_TOKEN: {'✅ OK' if BOT_TOKEN else '❌ ERROR'}")
print(f"   OPENAI_API_KEY: {'✅ OK' if OPENAI_API_KEY else '❌ ERROR'}")
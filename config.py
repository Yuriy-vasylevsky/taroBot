import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

raw_admin = os.getenv("ADMIN_ID")
ADMIN_ID = int(raw_admin) if raw_admin and raw_admin.strip().isdigit() else None


print(f"✅ ADMIN_ID завантажено: {ADMIN_ID} (тип: {type(ADMIN_ID)})")
print(f"   BOT_TOKEN: {'✅ OK' if BOT_TOKEN else '❌ ERROR'}")
print(f"   DEEPSEEK_API_KEY: {'✅ OK' if DEEPSEEK_API_KEY else '❌ ERROR'}")

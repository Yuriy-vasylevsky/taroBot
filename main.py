import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
from modules.menu import menu_router
from taro.card_of_day import card_router
from taro.ask_taro import ask_taro
from taro.dialog_tarot import dialog_router
from taro.yes_no import yes_no
from taro.plus_minus import plus_minus
from taro.you_other import you_other
from taro.horseshoe import horseshoe
from taro.love_dialog import love_taro
from modules.user_stats_db import init_db
from modules.admin_panel import admin_router
from modules.activity_logger import ActivityLoggerMiddleware
from modules.energy_panel import energy_router
from modules.start_handler import start_router
from modules.admin_users import admin_users_router

# ====================== WEBHOOK НАЛАШТУВАННЯ ======================
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # ← ОБОВ'ЯЗКОВО додай в Railway Variables!
PORT = int(os.getenv("PORT", 8080))

if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL не встановлений! Додай його в Railway Variables")

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# ====================== STARTUP / SHUTDOWN ======================
async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        drop_pending_updates=True,
    )
    print(f"✅ Webhook успішно встановлено → {WEBHOOK_URL}{WEBHOOK_PATH}")

async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    print("🛑 Webhook видалено при завершенні")

# ====================== ОСНОВНА ФУНКЦІЯ ======================
async def main():
    print("🔮 taroBot запускається...")

    # 1. Ініціалізація бази даних
    await init_db()

    # 2. Middleware
    logger_mw = ActivityLoggerMiddleware()
    dp.message.middleware(logger_mw)
    dp.callback_query.middleware(logger_mw)

    # 3. Підключаємо всі роутери
    dp.include_router(menu_router)
    dp.include_router(card_router)
    dp.include_router(ask_taro)
    dp.include_router(dialog_router)
    dp.include_router(yes_no)
    dp.include_router(plus_minus)
    dp.include_router(you_other)
    dp.include_router(horseshoe)
    dp.include_router(love_taro)
    dp.include_router(admin_router)
    dp.include_router(energy_router)
    dp.include_router(start_router)
    dp.include_router(admin_users_router)

    # Реєструємо startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ====================== ЗАПУСК WEBHOOK ======================
    app = web.Application()
    app["bot"] = bot

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    print(f"🚀 Запуск веб-сервера на порту {PORT}...")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
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


async def main():
    print("🔮 Бот запускається...")

    # 1) Створюємо таблиці для юзерів/логів
    await init_db()

    # 2) Бот і диспетчер
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),  
    )
    dp = Dispatcher()

    

    # 3) Мідлвар — ВАЖЛИВО: на message і callback_query, НЕ на update
    logger_mw = ActivityLoggerMiddleware()
    dp.message.middleware(logger_mw)
    dp.callback_query.middleware(logger_mw)

    # 4) Роутери
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
    # 5) Старт
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущено, слухаю апдейти...")
    await dp.start_polling(bot)


if __name__ == "__main__": 
    asyncio.run(main())

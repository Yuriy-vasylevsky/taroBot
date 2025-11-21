import os
import uuid
import random
import tempfile
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    FSInputFile,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from PIL import Image
import config
from cards_data import TAROT_CARDS
import asyncio
from aiogram import Bot, Dispatcher
import config

from modules.menu import menu_router
from modules.card_of_day import card_router
from modules.ask_taro import ask_taro
from modules.dialog_tarot import dialog_router
from modules.yes_no import yes_no
from modules.plus_minus import plus_minus
from modules.you_other import you_other
from modules.horseshoe import horseshoe


bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Підключаємо всі модулі
dp.include_router(menu_router)
dp.include_router(card_router)
dp.include_router(ask_taro)
dp.include_router(dialog_router)
dp.include_router(yes_no)
dp.include_router(plus_minus)
dp.include_router(you_other)
dp.include_router(horseshoe)


async def main():
    print("🔮 Бот запущено...")
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())

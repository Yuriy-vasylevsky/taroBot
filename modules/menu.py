from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from modules.animation import run_animation

menu_router = Router()

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🃏 Карта дня")],
        [KeyboardButton(text="💬 Діалог з Таро")],
        [KeyboardButton(text="🔮 Живий Таро-чат")],
        [KeyboardButton(text="✅ Так / Ні")],
    ],
    resize_keyboard=True,
)

@menu_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "🔮 Вітаю у Таро-боті!\n"
        "Обери розклад, щоб дізнатись, що карти кажуть сьогодні...",
        reply_markup=menu,
    )

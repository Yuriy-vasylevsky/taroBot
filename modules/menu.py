from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from modules.animation import run_animation  # якщо не треба – можеш видалити/закоментити

menu_router = Router()

# ======================
#   Головне меню
# ======================

# 🔗 ТУТ ПІДСТАВ СВІЙ ГОТОВИЙ WEBAPP ДЛЯ ПЕРЕГЛЯДУ ВСІХ КАРТ
VIEW_ALL_CARDS_URL = "https://yuriy-vasylevsky.github.io/webOllcads"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🃏 Карта дня")],
        [KeyboardButton(text="🔮 Живий Таро-чат")],
        [KeyboardButton(text="📚 Популярні розклади")],
        [
            KeyboardButton(
                text="🖼 Переглянути всі карти",
                web_app=WebAppInfo(url=VIEW_ALL_CARDS_URL),
            )
        ],
    ],
    resize_keyboard=True,
)

# Для сумісності з існуючим кодом
menu = main_menu


# ======================
#   Меню популярних розкладів
# ======================
popular_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Діалог з Таро")],
        [KeyboardButton(text="❤️ Любов / Стосунки")],
        [
            KeyboardButton(text="✅ Так / Ні"),
            KeyboardButton(text="➕➖ Плюси / Мінуси"),
        ],
        [KeyboardButton(text="👥 Ти / Інша людина")],
        [KeyboardButton(text="🍀 Підкова (7 карт)")],
        [KeyboardButton(text="⬅️ Назад в меню")],
    ],
    resize_keyboard=True,
)


# ======================
#   /start
# ======================
@menu_router.message(CommandStart())
async def start_cmd(message: types.Message):
    # Якщо хочеш анімацію при старті – розкоментуй:
    # await run_animation(message.bot, message.chat.id)

    await message.answer(
        "🔮 Вітаю у Таро-боті!\n"
        "Обери те, що тобі відгукується прямо зараз:",
        reply_markup=main_menu,
    )


# ======================
#   Вхід у меню популярних розкладів
# ======================
@menu_router.message(F.text == "📚 Популярні розклади")
async def open_popular_menu(message: types.Message):
    await message.answer(
        "📚 Популярні розклади:\n"
        "Обери формат, який підходить до твоєї ситуації:",
        reply_markup=popular_menu,
    )


# ======================
#   Назад у головне меню
# ======================
@menu_router.message(F.text == "⬅️ Назад в меню")
async def back_to_main_menu(message: types.Message):
    await message.answer(
        "🔙 Повертаю в головне меню.",
        reply_markup=main_menu,
    )

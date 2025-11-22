
# from aiogram import Router, types, F
# from aiogram.filters import CommandStart
# from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

# from modules.animation import run_animation  # якщо не треба – можеш видалити/закоментити
# import config  # тут має бути ADMIN_ID

# menu_router = Router()

# VIEW_ALL_CARDS_URL = "https://yuriy-vasylevsky.github.io/tarot-allcards"  # твій WebApp з усіма картами
# ADMIN_ID = 752963390


# # ======================
# #   Побудова головного меню (динамічна)
# # ======================
# def build_main_menu(user_id: int | None = None) -> ReplyKeyboardMarkup:
#     is_admin = user_id == ADMIN_ID

#     rows: list[list[KeyboardButton]] = []

#     # рядок для адміна
#     if is_admin:
#         rows.append([KeyboardButton(text="🛠 Адмін-панель")])

#     # звичайні кнопки
#     rows.extend(
#         [
#             [KeyboardButton(text="🃏 Карта дня")],
#             [KeyboardButton(text="🔮 Живий Таро-чат")],
#             [KeyboardButton(text="📚 Популярні розклади")],
#             [
#                 KeyboardButton(
#                     text="🖼 Переглянути всі карти",
#                     web_app=WebAppInfo(url=VIEW_ALL_CARDS_URL),
#                 )
#             ],
#         ]
#     )

#     return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# # Для сумісності зі старим кодом, який імпортує `menu`
# # (це меню без адмін-кнопки, для звичайних юзерів)
# menu = build_main_menu(user_id=None)


# # ======================
# #   Меню популярних розкладів
# # ======================
# popular_menu = ReplyKeyboardMarkup(
#     keyboard=[
#         [KeyboardButton(text="💬 Діалог з Таро")],
#         [KeyboardButton(text="❤️ Любов / Стосунки")],
#         [
#             KeyboardButton(text="✅ Так / Ні"),
#             KeyboardButton(text="➕➖ Плюси / Мінуси"),
#         ],
#         [KeyboardButton(text="👥 Ти / Інша людина")],
#         [KeyboardButton(text="🍀 Підкова (7 карт)")],
#         [KeyboardButton(text="⬅️ Назад в меню")],
#     ],
#     resize_keyboard=True,
# )

# # ======================
# #   Адмін-меню
# # ======================
# def admin_menu() -> ReplyKeyboardMarkup:
#     keyboard = [
#         ["👥 Користувачі"],
#         # сюди потім можна додати ще пункти (наприклад, керування енергією)
#         ["🔙 Назад в меню"],
#     ]

#     return ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
#         resize_keyboard=True,
#     )


# # ======================
# #   /start
# # ======================
# @menu_router.message(CommandStart())
# async def start_cmd(message: types.Message):
#     # Якщо хочеш анімацію при старті – розкоментуй:
#     # await run_animation(message.bot, message.chat.id)

#     kb = build_main_menu(message.from_user.id)

#     await message.answer(
#         "🔮 Вітаю у Таро-боті!\n"
#         "Обери те, що тобі відгукується прямо зараз:",
#         reply_markup=kb,
#     )


# # ======================
# #   Вхід у меню популярних розкладів
# # ======================
# @menu_router.message(F.text == "📚 Популярні розклади")
# async def open_popular_menu(message: types.Message):
#     await message.answer(
#         "📚 Популярні розклади:\n"
#         "Обери формат, який підходить до твоєї ситуації:",
#         reply_markup=popular_menu,
#     )


# # ======================
# #   Назад у головне меню
# # ======================
# @menu_router.message(F.text == "⬅️ Назад в меню")
# async def back_to_main_menu(message: types.Message):
#     kb = build_main_menu(message.from_user.id)

#     await message.answer(
#         "🔙 Повертаю в головне меню.",
#         reply_markup=kb,
#     )


from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from modules.animation import run_animation  # необов’язково
import config

menu_router = Router()

VIEW_ALL_CARDS_URL = "https://yuriy-vasylevsky.github.io/webOllcads"
ADMIN_ID = config.ADMIN_ID   # твоє значення 752963390


# ======================
#   ГОЛОВНЕ МЕНЮ (динамічне)
# ======================
def build_main_menu(user_id: int | None = None) -> ReplyKeyboardMarkup:
    is_admin = user_id == ADMIN_ID

    rows: list[list[KeyboardButton]] = []

    # Адміну показуємо кнопку
    if is_admin:
        rows.append([KeyboardButton(text="🛠 Адмін-панель")])

    # Основні кнопки
    rows.extend(
        [
            [KeyboardButton(text="🃏 Карта дня")],
            [KeyboardButton(text="🔮 Живий Таро-чат")],
            [KeyboardButton(text="📚 Популярні розклади")],
            [
                KeyboardButton(
                    text="🖼 Переглянути всі карти",
                    web_app=WebAppInfo(url=VIEW_ALL_CARDS_URL),
                )
            ],
        ]
    )

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# Сумісність зі старими модулями
menu = build_main_menu()


# ======================
#   МЕНЮ ПОПУЛЯРНИХ РОЗКЛАДІВ
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
        [KeyboardButton(text="🔙 Назад в меню")],
    ],
    resize_keyboard=True,
)


# ======================
#   АДМІН-МЕНЮ (теж тут)
# ======================
def admin_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        ["👥 Користувачі"],
        ["📈 Активність"],
        ["💰 Енергія користувачів"],
        ["🔙 Назад в меню"],
    ]

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in keyboard],
        resize_keyboard=True,
    )


# ======================
#   /start
# ======================
@menu_router.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = build_main_menu(message.from_user.id)

    await message.answer(
        "🔮 Вітаю у Таро-боті!\nОбери те, що тобі відгукується прямо зараз:",
        reply_markup=kb,
    )


# ======================
#   Вхід у популярні розклади
# ======================
@menu_router.message(F.text == "📚 Популярні розклади")
async def open_popular_menu(message: types.Message):
    await message.answer(
        "📚 Популярні розклади:",
        reply_markup=popular_menu,
    )


# ======================
#   Вхід у адмін-панель
# ======================
@menu_router.message(F.text == "🛠 Адмін-панель")
async def open_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У тебе немає доступу.")
        return

    await message.answer(
        "🛠 Адмін-панель:",
        reply_markup=admin_menu(),
    )


# ======================
#   Назад у головне меню
# ======================
@menu_router.message(F.text == "🔙 Назад в меню")
async def back_to_main_menu(message: types.Message):
    kb = build_main_menu(message.from_user.id)
    await message.answer("🔙 Повертаю в меню.", reply_markup=kb)

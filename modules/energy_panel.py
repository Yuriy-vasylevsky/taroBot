# from aiogram import Router, F, types
# from modules.user_stats_db import get_energy
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# energy_router = Router()

# # --------------------------
# #  Поповнення енергії (меню)
# # --------------------------
# @energy_router.message(F.text == "⚡ Поповнити енергію")
# async def open_energy_panel(message: types.Message):
#     user = message.from_user
#     energy = await get_energy(user.id)

#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="💛 Поповнити",
#                     callback_data="energy_topup"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="👥 Запросити друзів",
#                     callback_data="energy_invite"
#                 )
#             ]
#         ]
#     )

#     await message.answer(
#         f"⚡ <b>Енергетичний баланс</b>\n\n"
#         f"👤 {user.full_name}\n"
#         f"✨ Баланс: <b>{energy}</b> енергії\n\n"
#         f"Обери дію:",
#         reply_markup=kb,
#         parse_mode="HTML"
#     )


# # --------------------------
# #   Поповнення енергії
# # --------------------------
# @energy_router.callback_query(F.data == "energy_topup")
# async def topup_energy(callback: types.CallbackQuery):
#     await callback.answer()

#     # Тут ти зможеш підключити оплату / підписку / бонуси
#     await callback.message.answer(
#         "💛 Поповнення енергії скоро буде доступне.\n"
#         "Залишайтесь на зв'язку!",
#         parse_mode="HTML"
#     )


# # --------------------------
# #   Запросити друзів
# # --------------------------


# @energy_router.callback_query(F.data == "energy_invite")
# async def invite_friends(callback: types.CallbackQuery):
#     await callback.answer()

#     user_id = callback.from_user.id

#     # 🔥 Правильно отримуємо username бота в Aiogram 3.x
#     me = await callback.bot.get_me()
#     bot_username = me.username

#     invite_link = f"https://t.me/{bot_username}?start={user_id}"

#     await callback.message.answer(
#         "👥 <b>Запроси друзів</b>\n\n"
#         "За кожного друга, який запустить бота — ти отримаєш <b>+12 енергії</b> ✨\n\n"
#         "Надішли цю персональну лінку:\n\n"
#         f"<code>{invite_link}</code>",
#         parse_mode="HTML"
#     )

# modules/energy_panel.py
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from modules.user_stats_db import get_energy
import config

energy_router = Router()

# 🔗 Лінк на твій акаунт-касира
# Можеш винести в config.CASHIER_LINK, якщо хочеш
CASHIER_LINK = "https://t.me/your_username_here"  # 🔴 ЗАМІНИ на свій @username


# --------------------------
#  Поповнення енергії (меню)
# --------------------------
@energy_router.message(F.text == "⚡ Поповнити енергію")
async def open_energy_panel(message: types.Message):
    user = message.from_user
    energy = await get_energy(user.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💛 Написати касиру",
                    callback_data="energy_topup"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Запросити друзів",
                    callback_data="energy_invite"
                )
            ]
        ]
    )

    await message.answer(
        f"⚡ <b>Енергетичний баланс</b>\n\n"
        f"👤 {user.full_name}\n"
        f"✨ Баланс: <b>{energy}</b> енергії\n\n"
        f"Обери дію:",
        reply_markup=kb,
        parse_mode="HTML"
    )


# --------------------------
#   Кнопка «Написати касиру»
# --------------------------
@energy_router.callback_query(F.data == "energy_topup")
async def topup_energy(callback: types.CallbackQuery):
    await callback.answer()

    text = (
        "💳 <b>Оплата через касира</b>\n\n"
        "Щоб поповнити баланс енергії — напиши касиру в особисті повідомлення:\n\n"
        f"{CASHIER_LINK}\n\n"
        "Опиши, на скільки енергії хочеш поповнити баланс ✨"
    )

    await callback.message.answer(text, parse_mode="HTML")


# --------------------------
#   Запросити друзів
# --------------------------
@energy_router.callback_query(F.data == "energy_invite")
async def invite_friends(callback: types.CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    me = await callback.bot.get_me()
    bot_username = me.username

    invite_link = f"https://t.me/{bot_username}?start={user_id}"

    await callback.message.answer(
        "👥 <b>Запроси друзів</b>\n\n"
        "За кожного друга, який запустить бота — ти отримаєш <b>+12 енергії</b> ✨\n\n"
        "Надішли цю персональну лінку:\n\n"
        f"<code>{invite_link}</code>",
        parse_mode="HTML"
    )

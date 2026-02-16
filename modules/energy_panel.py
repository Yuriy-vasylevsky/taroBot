
# from aiogram import Router, F, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from modules.user_stats_db import get_energy
# import config

# energy_router = Router()

# # 🔗 Лінк на твій акаунт-касира
# # Можеш винести в config.CASHIER_LINK, якщо хочеш
# CASHIER_LINK = "https://t.me/your_username_here"  # 🔴 ЗАМІНИ на свій @username


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
#                     text="💛 Написати касиру",
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


# # # --------------------------
# # #   Кнопка «Написати касиру»
# # # --------------------------
# # @energy_router.callback_query(F.data == "energy_topup")
# # async def topup_energy(callback: types.CallbackQuery):
# #     await callback.answer()

# #     text = (
# #         "💳 <b>Оплата через касира</b>\n\n"
# #         "Щоб поповнити баланс енергії — напиши касиру в особисті повідомлення:\n\n"
# #         f"{CASHIER_LINK}\n\n"
# #         "Опиши, на скільки енергії хочеш поповнити баланс ✨"
# #     )

# #     await callback.message.answer(text, parse_mode="HTML")


# # # --------------------------
# # #   Запросити друзів
# # # --------------------------
# # @energy_router.callback_query(F.data == "energy_invite")
# # async def invite_friends(callback: types.CallbackQuery):
# #     await callback.answer()

# #     user_id = callback.from_user.id

# #     me = await callback.bot.get_me()
# #     bot_username = me.username

# #     invite_link = f"https://t.me/{bot_username}?start={user_id}"

# #     await callback.message.answer(
# #         "👥 <b>Запроси друзів</b>\n\n"
# #         "За кожного друга, який запустить бота — ти отримаєш <b>+12 енергії</b> ✨\n\n"
# #         "Надішли цю персональну лінку:\n\n"
# #         f"<code>{invite_link}</code>",
# #         parse_mode="HTML"
# #     )


# # from __future__ import annotations

# from aiogram import Router, types, F
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# from modules.user_stats_db import get_energy


# energy_router = Router()

# # налаштування (можеш винести в config)
# CASHIER_LINK = "https://t.me/your_username_here"
# BOT_USERNAME = "minions_taro_bot"  # тільки username, без @


# def energy_panel_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
#             [InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")],
#             [InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")],
#         ]
#     )


# async def open_energy_panel_here(message: types.Message, *, title: str = "⚡ <b>Енергетичний баланс</b>"):
#     user = message.from_user
#     energy = await get_energy(user.id)
#     await message.answer(
#         f"{title}\n\n"
#         f"👤 {user.full_name}\n"
#         f"✨ Баланс: <b>{energy}</b> енергії\n\n"
#         f"Обери дію:",
#         reply_markup=energy_panel_kb(),
#         parse_mode="HTML",
#     )


# async def _safe_edit_or_ignore(
#     msg: types.Message,
#     text: str,
#     reply_markup: InlineKeyboardMarkup,
#     *,
#     parse_mode: str = "HTML",
# ) -> bool:
#     """
#     True  – якщо відредагували
#     False – якщо не редагували (message is not modified)
#     """
#     try:
#         await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
#         return True
#     except TelegramBadRequest as e:
#         s = str(e).lower()
#         if "message is not modified" in s:
#             return False
#         raise


# @energy_router.callback_query(F.data == "energy_invite")
# async def energy_invite(callback: types.CallbackQuery):
#     await callback.answer()

#     user_id = callback.from_user.id
#     link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

#     text = (
#         "👥 <b>Запроси друзів</b>\n\n"
#         "За кожного друга, який запустить бота – ти отримаєш <b>+12</b> енергії ✨\n\n"
#         "Надішли цю персональну лінку:\n\n"
#         f"{link}"
#     )

#     try:
#         edited = await _safe_edit_or_ignore(callback.message, text, energy_panel_kb(), parse_mode="HTML")
#         if not edited:
#             return
#     except TelegramBadRequest:
#         await callback.message.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


# @energy_router.callback_query(F.data == "energy_topup")
# async def energy_topup(callback: types.CallbackQuery):
#     await callback.answer()

#     text = (
#         "💳 <b>Оплата через касира</b>\n\n"
#         "Щоб поповнити баланс енергії – напиши касиру в особисті повідомлення:\n\n"
#         f"{CASHIER_LINK}\n\n"
#         "Опиши, на скільки енергії хочеш поповнити баланс ✨"
#     )

#     try:
#         edited = await _safe_edit_or_ignore(callback.message, text, energy_panel_kb(), parse_mode="HTML")
#         if not edited:
#             return
#     except TelegramBadRequest:
#         await callback.message.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


# @energy_router.callback_query(F.data == "energy_back_menu")
# async def energy_back_menu(callback: types.CallbackQuery):
#     await callback.answer()

#     # локальний імпорт щоб не робити циклічних імпортів
#     from modules.menu import build_main_menu

#     user_id = callback.from_user.id
#     kb = build_main_menu(user_id)

#     # 1) прибираємо панель (видаляємо повідомлення з кнопками)
#     try:
#         await callback.message.delete()
#     except (TelegramBadRequest, TelegramForbiddenError):
#         try:
#             await callback.message.edit_reply_markup(reply_markup=None)
#         except Exception:
#             pass

#     # 2) показуємо головне меню окремим повідомленням
#     await callback.message.bot.send_message(
#         chat_id=callback.message.chat.id,
#         text="🔙 Повертаємось в головне меню",
#         reply_markup=kb,
#     )


from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from modules.user_stats_db import get_energy

energy_router = Router()

CASHIER_LINK = "https://t.me/your_username_here"   # заміни
BOT_USERNAME = "minions_taro_bot"                  # заміни якщо інший


def energy_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
            [InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")],
            [InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")],
        ]
    )


def build_no_energy_kb() -> types.InlineKeyboardMarkup:
    """
    Клавіатура, коли недостатньо енергії.
    Кнопки інтегровані з energy_router.py:
    - energy_topup - написати касиру
    - energy_invite - запросити друзів
    """
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="💛 Написати касиру",
                    callback_data="energy_topup"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="👥 Запросити друзів",
                    callback_data="energy_invite"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🏠 Повернутись в меню",
                    callback_data="back_to_main_menu"
                )
            ]
        ]
    )



async def open_energy_panel_here(message: types.Message, *, title: str = "⚡ <b>Енергетичний баланс</b>"):
    user = message.from_user
    energy = await get_energy(user.id)
    await message.answer(
        f"{title}\n\n"
        f"👤 {user.full_name}\n"
        f"✨ Баланс: <b>{energy}</b> енергії\n\n"
        f"Обери дію:",
        reply_markup=energy_panel_kb(),
        parse_mode="HTML",
    )


# ✅ ВХІД З ГОЛОВНОГО МЕНЮ (ось чого тобі зараз не вистачає)
@energy_router.message(F.text == "⚡ Поповнити енергію")
async def open_energy_panel_from_menu(message: types.Message):
    await open_energy_panel_here(message)


async def _safe_edit_or_ignore(
    msg: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    *,
    parse_mode: str = "HTML",
) -> bool:
    try:
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "message is not modified" in s:
            return False
        raise


@energy_router.callback_query(F.data == "energy_invite")
async def energy_invite(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    text = (
        "👥 <b>Запроси друзів</b>\n\n"
        "За кожного друга, який запустить бота – ти отримаєш <b>+12</b> енергії ✨\n\n"
        "Надішли цю персональну лінку:\n\n"
        f"{link}"
    )

    try:
        edited = await _safe_edit_or_ignore(callback.message, text, energy_panel_kb(), parse_mode="HTML")
        if not edited:
            return
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


@energy_router.callback_query(F.data == "energy_topup")
async def energy_topup(callback: types.CallbackQuery):
    await callback.answer()

    text = (
        "💳 <b>Оплата через касира</b>\n\n"
        "Щоб поповнити баланс енергії – напиши касиру в особисті повідомлення:\n\n"
        f"{CASHIER_LINK}\n\n"
        "Опиши, на скільки енергії хочеш поповнити баланс ✨"
    )

    try:
        edited = await _safe_edit_or_ignore(callback.message, text, energy_panel_kb(), parse_mode="HTML")
        if not edited:
            return
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


@energy_router.callback_query(F.data == "energy_back_menu")
async def energy_back_menu(callback: types.CallbackQuery):
    await callback.answer()

    from modules.menu import build_main_menu

    user_id = callback.from_user.id
    kb = build_main_menu(user_id)

    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text="🔙 Повертаємось в головне меню",
        reply_markup=kb,
    )



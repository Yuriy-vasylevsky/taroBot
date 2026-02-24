
# from aiogram import Router, types, F
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
# from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
# from modules.user_stats_db import get_energy, add_energy
# import urllib.parse

# energy_router = Router()

# CASHIER_LINK = "t.me/minion_taro_kassa"
# BOT_USERNAME = "minions_taro_bot"


# # ====================== СУМІСНІСТЬ З КАРТОЮ ДНЯ ======================
# def build_no_energy_kb() -> InlineKeyboardMarkup:
#     """
#     Залишаємо для сумісності з taro/ask_taro.py
#     (коли енергії недостатньо — показуємо ту саму панель)
#     """
#     return energy_panel_kb()

# # ====================== КЛАВІАТУРИ ======================
# def energy_panel_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
#             [InlineKeyboardButton(text="⭐ Купити за Зірочки", callback_data="energy_topup_stars")],
#             [InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")],
#             [InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")],
#         ]
#     )


# def build_stars_packages_kb() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text=f"⚡ 20 енергії — 50 ⭐", callback_data="stars_pack_20")],
#             [InlineKeyboardButton(text=f"⚡ 50 енергії — 125 ⭐", callback_data="stars_pack_50")],
#             [InlineKeyboardButton(text=f"⚡ 100 енергії — 220 ⭐", callback_data="stars_pack_100")],
#             [InlineKeyboardButton(text="🔙 Назад до панелі", callback_data="energy_back_to_panel")],
#         ]
#     )


# def build_invite_friends_kb(link: str) -> InlineKeyboardMarkup:
#     share_text = "🔮 Приєднуйся до мене в найкращому 🃏 Таро боті!\n\n✨ +12 енергії в подарунок ✨\n"
#     encoded_text = urllib.parse.quote(share_text)
#     share_url = f"https://t.me/share/url?url={link}&text={encoded_text}"

#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="🔗 Поділитися посиланням", url=share_url)],
#             [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
#             [InlineKeyboardButton(text="⭐ Купити за Зірочки", callback_data="energy_topup_stars")],
#             [InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")],
#         ]
#     )


# # ====================== УНІВЕРСАЛЬНА ФУНКЦІЯ РЕДАГУВАННЯ ======================
# async def show_energy_panel(callback_or_message, title: str = "⚡ <b>Енергетичний баланс</b>"):
#     """Редагує поточне повідомлення або надсилає нове (якщо потрібно)"""
#     if isinstance(callback_or_message, types.CallbackQuery):
#         msg = callback_or_message.message
#         user = callback_or_message.from_user
#     else:
#         msg = callback_or_message
#         user = callback_or_message.from_user

#     energy = await get_energy(user.id)

#     text = (
#         f"{title}\n\n"
#         f"👤 {user.full_name}\n"
#         f"✨ Баланс: <b>{energy}</b> енергії\n\n"
#         f"Обери дію:"
#     )

#     try:
#         await msg.edit_text(text, reply_markup=energy_panel_kb(), parse_mode="HTML")
#     except TelegramBadRequest as e:
#         if "message is not modified" not in str(e).lower():
#             await msg.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


# # ====================== ХЕНДЛЕРИ ======================
# @energy_router.message(F.text == "⚡ Поповнити енергію")
# async def open_energy_panel_from_menu(message: types.Message):
#     await show_energy_panel(message)


# @energy_router.callback_query(F.data == "energy_invite")
# async def energy_invite(callback: types.CallbackQuery):
#     await callback.answer()
#     user_id = callback.from_user.id
#     link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

#     text = (
#         "👥 <b>Запроси друзів</b>\n\n"
#         "За кожного друга, який запустить бота – ти отримаєш <b>+12</b> енергії ✨\n\n"
#         f"Твоє посилання:\n<code>{link}</code>"
#     )
#     kb = build_invite_friends_kb(link)

#     try:
#         await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
#     except TelegramBadRequest:
#         await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# @energy_router.callback_query(F.data == "energy_topup")
# async def energy_topup(callback: types.CallbackQuery):
#     await callback.answer()
#     text = (
#         "💳 <b>Оплата через касира</b>\n\n"
#         "<b>⚡ 20 </b> - 50 грн \n"
#         "<b>⚡ 50 </b> - 150 грн \n"
#         "<b>⚡ 100 </b> - 200 грн \n\n"
#         f"{CASHIER_LINK}\n\n"
#     )
#     try:
#         await callback.message.edit_text(text, reply_markup=energy_panel_kb(), parse_mode="HTML")
#     except TelegramBadRequest:
#         await callback.message.answer(text, reply_markup=energy_panel_kb(), parse_mode="HTML")


# @energy_router.callback_query(F.data == "energy_topup_stars")
# async def energy_topup_stars(callback: types.CallbackQuery):
#     await callback.answer()
#     text = (
#         "⭐ <b>Поповнення за Зірочки Telegram</b>\n\n"
#         "Обирай пакет — оплата миттєво в чаті ✨\n"
#         "Без реквізитів, без ФОП, працює навіть на iOS"
#     )
#     try:
#         await callback.message.edit_text(text, reply_markup=build_stars_packages_kb(), parse_mode="HTML")
#     except TelegramBadRequest:
#         await callback.message.answer(text, reply_markup=build_stars_packages_kb(), parse_mode="HTML")

# # ==========================================================
# @energy_router.callback_query(F.data.startswith("stars_pack_"))
# async def buy_stars_pack(callback: types.CallbackQuery):
#     await callback.answer("Відкриваю форму оплати...")
#     pack_id = callback.data.split("_")[-1]
#     packs = {"20": (1, 20), "50": (125, 50), "100": (220, 100)}
#     stars, energy = packs[pack_id]

#     await callback.bot.send_invoice(
#         chat_id=callback.message.chat.id,
#         title=f"⚡ {energy} енергії",
#         description=f"Миттєве поповнення на {energy} енергії ✨",
#         payload=f"energy_pack_{pack_id}",
#         provider_token="",
#         currency="XTR",
#         prices=[LabeledPrice(label=f"{energy} енергії", amount=stars)],
#     )


# @energy_router.callback_query(F.data == "energy_back_to_panel")
# async def energy_back_to_panel(callback: types.CallbackQuery):
#     await callback.answer()
#     await show_energy_panel(callback)   # ← тепер редагує поточне повідомлення!


# @energy_router.callback_query(F.data == "energy_back_menu")
# async def energy_back_menu(callback: types.CallbackQuery):
#     await callback.answer()
#     from modules.menu import build_main_menu
#     kb = build_main_menu(callback.from_user.id)

#     try:
#         await callback.message.delete()
#     except Exception:
#         pass

#     await callback.message.bot.send_message(
#         callback.message.chat.id,
#         "🔙 Повертаємось в головне меню",
#         reply_markup=kb,
#     )


# # ====================== ОБРОБКА ПЛАТЕЖІВ ======================
# @energy_router.pre_checkout_query()
# async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
#     await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# @energy_router.message(F.successful_payment)
# async def successful_payment_handler(message: types.Message):
#     payment = message.successful_payment
#     if payment.currency != "XTR" or not payment.invoice_payload.startswith("energy_pack_"):
#         return

#     pack_id = payment.invoice_payload.split("_")[-1]
#     energy_to_add = {"20": 20, "50": 50, "100": 100}[pack_id]

#     await add_energy(message.from_user.id, energy_to_add)

#     await message.answer(
#         f"✅ <b>Дякуємо!</b>\n\n"
#         f"✨ +{energy_to_add} енергії додано\n"
#         f"Баланс оновлено 🔥",
#         parse_mode="HTML"
#     )

#     # Показуємо оновлену панель (без дублювання)
#     await show_energy_panel(message, title="⚡ <b>Баланс оновлено!</b>")

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramBadRequest
from modules.user_stats_db import get_energy, add_energy
import urllib.parse

energy_router = Router()

CASHIER_LINK = "t.me/minion_taro_kassa"
BOT_USERNAME = "minions_taro_bot"


# ====================== ДИНАМІЧНІ КЛАВІАТУРИ ======================
def build_energy_keyboard(state: str = "main") -> InlineKeyboardMarkup:
    """Головний генератор клавіатур. Приховує кнопку поточного меню"""
    buttons = []

    if state != "cashier":
        buttons.append([InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")])
    if state != "stars":
        buttons.append([InlineKeyboardButton(text="⭐ Купити за Зірочки", callback_data="energy_topup_stars")])
    if state != "invite":
        buttons.append([InlineKeyboardButton(text="👥 Запросити друзів", callback_data="energy_invite")])

    buttons.append([InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ====================== СУМІСНІСТЬ З ІНШИМИ МОДУЛЯМИ ======================
def build_no_energy_kb() -> InlineKeyboardMarkup:
    """
    Ця функція використовується в taro/ask_taro.py та інших файлах,
    коли енергії недостатньо. Тепер вона повертає сучасну клавіатуру.
    """
    return build_energy_keyboard(state="main")


def build_stars_packages_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ 20 енергії — 50 ⭐", callback_data="stars_pack_20")],
            [InlineKeyboardButton(text="⚡ 50 енергії — 125 ⭐", callback_data="stars_pack_50")],
            [InlineKeyboardButton(text="⚡ 100 енергії — 220 ⭐", callback_data="stars_pack_100")],
            [InlineKeyboardButton(text="🔙 Назад до панелі", callback_data="energy_back_to_panel")],
        ]
    )


def build_invite_friends_kb(link: str) -> InlineKeyboardMarkup:
    share_text = "🔮 Приєднуйся до мене в найкращому 🃏 Таро боті!\n\n✨ +12 енергії в подарунок ✨\n"
    encoded_text = urllib.parse.quote(share_text)
    share_url = f"https://t.me/share/url?url={link}&text={encoded_text}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Поділитися посиланням", url=share_url)],
            [InlineKeyboardButton(text="💛 Написати касиру", callback_data="energy_topup")],
            [InlineKeyboardButton(text="⭐ Купити за Зірочки", callback_data="energy_topup_stars")],
            [InlineKeyboardButton(text="🏠 Повернутись в меню", callback_data="energy_back_menu")],
        ]
    )


# ====================== УНІВЕРСАЛЬНЕ ПОКАЗУВАННЯ ======================
async def show_energy_panel(callback_or_message, title: str = "⚡ <b>Енергетичний баланс</b>", state: str = "main"):
    if isinstance(callback_or_message, types.CallbackQuery):
        msg = callback_or_message.message
        user = callback_or_message.from_user
    else:
        msg = callback_or_message
        user = callback_or_message.from_user

    energy = await get_energy(user.id)

    text = (
        f"{title}\n\n"
        f"👤 {user.full_name}\n"
        f"✨ Баланс: <b>{energy}</b> енергії\n\n"
        f"Обери дію:"
    )

    kb = build_energy_keyboard(state)

    try:
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            await msg.answer(text, reply_markup=kb, parse_mode="HTML")


# ====================== ХЕНДЛЕРИ ======================
@energy_router.message(F.text == "⚡ Поповнити енергію")
async def open_energy_panel_from_menu(message: types.Message):
    await show_energy_panel(message, state="main")


@energy_router.callback_query(F.data == "energy_topup")
async def energy_topup(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "💳 <b>Оплата через касира</b>\n\n"
        "<b>⚡ 20 </b> - 50 грн \n"
        "<b>⚡ 50 </b> - 150 грн \n"
        "<b>⚡ 100 </b> - 200 грн \n\n"
        f"{CASHIER_LINK}\n\n"
    )
    try:
        await callback.message.edit_text(text, reply_markup=build_energy_keyboard(state="cashier"), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=build_energy_keyboard(state="cashier"), parse_mode="HTML")


@energy_router.callback_query(F.data == "energy_topup_stars")
async def energy_topup_stars(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "⭐ <b>Поповнення за Зірочки Telegram</b>\n\n"
        "Обирай пакет — оплата миттєво в чаті ✨\n"
        "Без реквізитів, без ФОП, працює навіть на iOS"
    )
    try:
        await callback.message.edit_text(text, reply_markup=build_stars_packages_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=build_stars_packages_kb(), parse_mode="HTML")


@energy_router.callback_query(F.data.startswith("stars_pack_"))
async def buy_stars_pack(callback: types.CallbackQuery):
    await callback.answer("Відкриваю форму оплати...")
    pack_id = callback.data.split("_")[-1]
    packs = {"20": (50, 20), "50": (125, 50), "100": (220, 100)}
    stars, energy = packs[pack_id]

    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"⚡ {energy} енергії",
        description=f"Миттєве поповнення на {energy} енергії ✨",
        payload=f"energy_pack_{pack_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{energy} енергії", amount=stars)],
    )


@energy_router.callback_query(F.data == "energy_invite")
async def energy_invite(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    text = (
        "👥 <b>Запроси друзів</b>\n\n"
        "За кожного друга, який запустить бота – ти отримаєш <b>+12</b> енергії ✨\n\n"
        f"Твоє посилання:\n<code>{link}</code>"
    )
    kb = build_invite_friends_kb(link)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@energy_router.callback_query(F.data == "energy_back_to_panel")
async def energy_back_to_panel(callback: types.CallbackQuery):
    await callback.answer()
    await show_energy_panel(callback, state="main")


@energy_router.callback_query(F.data == "energy_back_menu")
async def energy_back_menu(callback: types.CallbackQuery):
    await callback.answer()
    from modules.menu import build_main_menu
    kb = build_main_menu(callback.from_user.id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.bot.send_message(
        callback.message.chat.id,
        "🔙 Повертаємось в головне меню",
        reply_markup=kb,
    )


# ====================== ПЛАТЕЖІ ======================
@energy_router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@energy_router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment = message.successful_payment
    if payment.currency != "XTR" or not payment.invoice_payload.startswith("energy_pack_"):
        return

    pack_id = payment.invoice_payload.split("_")[-1]
    energy_to_add = {"20": 20, "50": 50, "100": 100}[pack_id]

    await add_energy(message.from_user.id, energy_to_add)

    await message.answer(
        f"✅ <b>Дякуємо!</b>\n\n"
        f"✨ +{energy_to_add} енергії додано\n"
        f"Баланс оновлено 🔥",
        parse_mode="HTML"
    )

    await show_energy_panel(message, title="⚡ <b>Баланс оновлено!</b>", state="main")
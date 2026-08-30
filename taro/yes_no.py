
import os
import json
import tempfile
import asyncio

from aiogram import Router, F, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from PIL import Image, ImageDraw, ImageFilter

from modules.menu import menu, popular_menu
from modules.energy_panel import build_no_energy_kb
from modules.telegram_text import answer_long_text, clean_generated_text
from modules.spread_extension import offer_spread_extension
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config

from modules.user_stats_db import get_energy, change_energy


yes_no = Router()
client = AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)

# ======================
#    НАЛАШТУВАННЯ ЕНЕРГІЇ
# ======================
ENERGY_COST_YESNO = 2  


async def charge_energy(user_id: int, cost: int):
    """
    Повертає:
    (True, new_balance) — якщо списано
    (False, current_balance) — якщо не вистачає
    """
    current = await get_energy(user_id)
    if current < cost:
        return False, current

    await change_energy(user_id, -cost)
    return True, current - cost


# ======================
#   ХЕЛПЕРИ ДЛЯ ПОВІДОМЛЕНЬ ДІАЛОГУ
# ======================
async def remember_dialog_msg(state: FSMContext, message: types.Message):
    """
    Запам'ятати message_id службового повідомлення діалогу.
    """
    data = await state.get_data()
    ids = data.get("dialog_msg_ids", [])
    ids.append(message.message_id)
    await state.update_data(dialog_msg_ids=ids)


async def clear_dialog_messages(state: FSMContext, bot, chat_id: int):
    """
    Видалити всі службові повідомлення діалогу, які зберігаємо в dialog_msg_ids.
    """
    data = await state.get_data()
    ids = data.get("dialog_msg_ids", [])

    for mid in ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass

    # щоб не намагатись чистити повторно
    await state.update_data(dialog_msg_ids=[])


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_YESNO = """
Ти — досвідчений таролог.
Твоє завдання — дати чітку відповідь: Так / Скоріше так / Нейтрально / Скоріше ні / Ні.
Поясни це на основі трьох карт:

1 — Основна енергія
2 — Прихована причина
3 — Ймовірний результат

Пиши лаконічно, тепло й конкретно. Відділяй блоки одним порожнім рядком.
Доречні емодзі вітаються, але не перевантажуй ними текст.
Не використовуй Markdown, HTML, зірочки, решітки та декоративні символи.

Структура:
🔮 Відповідь: один чіткий варіант і коротке пояснення.
🃏 Що показують карти: по одному стислому реченню на кожну карту.
🌙 Висновок: 1–2 речення.
💡 Порада: один практичний крок.
"""


# ======================
#      FSM STATES
# ======================
class YesNoFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 3 КАРТ
# ======================
def combine_yesno_cards(paths, uprights, background="background.png"):

    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop(img):
        dpi = img.info.get("dpi", (300, 300))[0]
        px = int((1 * dpi) / 25.4)
        return img.crop((px, px, img.size[0] - px, img.size[1] - px))

    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius, fill=255)
        result = Image.new("RGBA", img.size)
        result.paste(img, mask=mask)
        return result

    def add_shadow(img, offset=(12, 18), blur=38):
        w, h = img.size
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 180))
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.paste(shadow, offset, shadow)
        layer.paste(img, (0, 0), img)
        return layer

    cards = []
    for p, u in zip(paths, uprights):
        img = Image.open(p).convert("RGBA")
        img = crop(img)
        if not u:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = add_shadow(img)
        cards.append(img)

    cw = int(W * 0.27)
    ratio = cw / cards[0].size[0]
    ch = int(cards[0].size[1] * ratio)
    cards = [c.resize((cw, int(ch * 1.05)), Image.LANCZOS) for c in cards]

    spacing = int(W * 0.03)
    total_width = cw * 3 + spacing * 2
    start_x = (W - total_width) // 2
    y = (H - ch) // 2

    for i, c in enumerate(cards):
        bg.alpha_composite(c, (start_x + i * (cw + spacing), y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG")
    return temp.name


# ======================
#  GPT ТЛУМАЧЕННЯ YES/NO
# ======================
async def interpret_yes_no(question: str, cards_display: str):
    prompt = (
        f"{SYSTEM_PROMPT_YESNO}\n\n"
        f"Питання:\n{question}\n\n"
        f"Карти:\n{cards_display}\n\n"
        "Зроби чіткий висновок Так / Скоріше так / Нейтрально / Скоріше ні / Ні."
    )

    resp = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_YESNO},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
    )

    return clean_generated_text(resp.choices[0].message.content)


# ======================
#   КНОПКА "НАЗАД" ДЛЯ YES/NO
# ======================
def build_back_yesno_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню розкладів",
                    callback_data="yesno_back_start",
                )
            ]
        ]
    )


# ======================
#       КНОПКА СТАРТ
# ======================
@yes_no.message(F.text == "✅ Так / Ні")
async def yesno_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(YesNoFSM.waiting_for_question)

    # 1) просимо ввести питання і прибираємо reply-клавіатуру
    msg = await message.answer(
        "❓ Напиши питання, на яке хочеш отримати відповідь Так / Ні:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.update_data(dialog_msg_ids=[msg.message_id])
    
    # 2) окремим повідомленням – інлайн "назад"
    msg_back = await message.answer(
        "💬",
        reply_markup=build_back_yesno_kb(),
    )
    await remember_dialog_msg(state, msg_back)


# ======================
#   НАЗАД ПІД ЧАС ВВОДУ ПИТАННЯ
# ======================
@yes_no.callback_query(YesNoFSM.waiting_for_question, F.data == "yesno_back_start")
async def yesno_back_from_question(callback: types.CallbackQuery, state: FSMContext):
    await clear_dialog_messages(
        state=state,
        bot=callback.message.bot,
        chat_id=callback.message.chat.id,
    )

    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text="📚 Повертаю в меню популярних розкладів.",
        reply_markup=popular_menu,
    )

    await state.clear()
    await callback.answer()


# ======================
#       ПИТАННЯ
# ======================
@yes_no.message(YesNoFSM.waiting_for_question)
async def yesno_question(message: types.Message, state: FSMContext):
    question = (message.text or "").strip()
    
    if not question:
        await message.answer("Будь ласка, сформулюй питання текстом.")
        return
    
    await state.update_data(question=question)

    # Інлайн-кнопки оплати бананами + "назад в меню"
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"🍌 Витратити {ENERGY_COST_YESNO} банани",
                    callback_data="yesno_pay"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню",
                    callback_data="yesno_back"
                )
            ]
        ]
    )

    msg = await message.answer(
        "✨ Сфокусуйтесь на своєму питанні та оплатіть розклад бананами 🍌\n",
        reply_markup=kb
    )
    await remember_dialog_msg(state, msg)

    await state.set_state(YesNoFSM.waiting_for_energy)


# ======================
#   ОПЛАТА / НАЗАД
# ======================
@yes_no.callback_query(YesNoFSM.waiting_for_energy)
async def yesno_energy_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # 🔙 Назад в меню
    if data == "yesno_back":
        await clear_dialog_messages(
            state=state,
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
        )

        await callback.message.bot.send_message(
            chat_id=callback.message.chat.id,
            text="📚 Повертаю в меню популярних розкладів.",
            reply_markup=popular_menu,
        )

        await state.clear()
        await callback.answer()
        return

    # Не оплата
    if data != "yesno_pay":
        await callback.answer()
        return

    await callback.answer()

    # 1) Перевіряємо та списуємо банани
    ok, value = await charge_energy(user_id, ENERGY_COST_YESNO)
    
    if not ok:
        current = value
        need = ENERGY_COST_YESNO
        user = callback.from_user
        
        await msg.answer(
            f"🍌 <b>Недостатньо бананів</b> — щоб зробити розклад, поповніть баланс.\n\n"
            f"Обери дію:",
            parse_mode="HTML",
            reply_markup=build_no_energy_kb()
        )
        
        # Очищаємо стан після показу помилки
        await state.clear()
        return

    # 2) видаляємо попереднє повідомлення з кнопками
    try:
        await msg.delete()
    except Exception:
        pass

    # 3) Анімація оплати бананами
    anim_msg = await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text="🍌 Передаємо банани колоді… ✨",
    )

    try:
        for i in range(4):
            bar = "✨" * (i + 1)
            try:
                await anim_msg.edit_text(f"🍌 Передаємо банани колоді… {bar}")
            except Exception:
                break
            await asyncio.sleep(0.3)
    except Exception:
        pass

    # 4) Ховаємо анімацію
    try:
        await anim_msg.delete()
    except Exception:
        pass

    # 5) Повідомлення "обмін успішний"
    left = value
    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text=(
            "🍌 Оплата успішна!\n"
            f"Ваш баланс: <b>{left}</b> бананів"
        ),
        parse_mode="HTML",
    )

    # 6) Показуємо кнопку WebApp для вибору 3 карт + кнопку повернутись в меню
    kb_reply = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                types.KeyboardButton(
                    text="✨ Обрати 3 карти",
                    web_app=types.WebAppInfo(
                        url="https://yuriy-vasylevsky.github.io/tarodayweb"
                    ),
                )
            ]
        ],
    )

    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text="🃏 Тепер оберіть 3 карти через колоду нижче:",
        reply_markup=kb_reply,
    )

    await state.set_state(YesNoFSM.waiting_for_cards)


# ======================
#      КАРТИ З WEBAPP
# ======================
@yes_no.message(YesNoFSM.waiting_for_cards, F.web_app_data)
async def yesno_cards(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer(
            "Не вдалося прочитати дані з колоди. Спробуй ще раз.",
            reply_markup=popular_menu
        )
        await state.clear()
        return

    if data.get("action") != "three_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 3:
        await message.answer(
            "Для цього розкладу потрібно саме 3 карти.",
            reply_markup=popular_menu
        )
        await state.clear()
        return

    state_data = await state.get_data()
    question = state_data.get("question")

    if not question:
        await message.answer(
            "Щось пішло не так. Спробуй почати розклад заново.",
            reply_markup=popular_menu
        )
        await state.clear()
        return

    img_paths = []
    uprights = []
    cards_display = []

    for i, card in enumerate(chosen, start=1):
        eng = card.get("name")
        up = bool(card.get("upright", True))

        info = TAROT_CARDS.get(eng)
        if not info:
            continue

        img_paths.append(info["image"])
        uprights.append(up)

        ua = info["ua_name"]
        arrow = "⬆️" if up else "⬇️"
        cards_display.append(f"{i}. {ua} {arrow}")

    if len(img_paths) != 3:
        await message.answer(
            "Не вдалося завантажити всі три карти.",
            reply_markup=popular_menu
        )
        await state.clear()
        return

    # 1) Комбінуємо 3 карти в одне зображення
    final_img = combine_yesno_cards(img_paths, uprights)

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Так / Ні"
    )

    # 2) Анімація "тлумачення…"
    load_msg = await message.answer("🔮 Тлумачення…")

    async def anim():
        i = 0
        while True:
            try:
                await load_msg.edit_text("🔮 Тлумачення…\n" + "🔮" * ((i % 5) + 1))
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    anim_task = asyncio.create_task(anim())

    # 3) GPT інтерпретація
    try:
        interpretation = await interpret_yes_no(question, "\n".join(cards_display))
    finally:
        anim_task.cancel()
        try:
            await load_msg.delete()
        except Exception:
            pass

    # 4) Відповідь користувачу
    await answer_long_text(
        message,
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>🔮 Розклад:</b> Так / Ні\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=popular_menu
    )
    await offer_spread_extension(
        message,
        question=question,
        spread_name="Так / Ні",
        original_interpretation=interpretation,
        excluded_cards=[card.get("name") for card in chosen],
    )

    # Чистимо тимчасовий файл
    try:
        os.remove(final_img)
    except Exception:
        pass

    await state.clear()


# # ======================
# #   ОБРОБНИК КНОПКИ "ПОВЕРНЕННЯ В МЕНЮ"
# # ======================
# @yes_no.callback_query(F.data == "back_to_main_menu")
# async def back_to_main_menu_callback(callback: types.CallbackQuery, state: FSMContext):
#     """
#     Повернення в головне меню
#     """
#     await callback.message.answer(
#         "🏠 Повертаємось в головне меню",
#         reply_markup=menu
#     )
#     await callback.answer()
#     await state.clear()

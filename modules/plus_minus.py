import os
import json
import tempfile
import asyncio

from aiogram import Router, F, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from PIL import Image, ImageDraw, ImageFilter

from modules.menu import menu, build_main_menu
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config

from modules.user_stats_db import get_energy, change_energy


plus_minus = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#    ЕНЕРГІЯ
# ======================
ENERGY_COST_PLUS_MINUS = 2  # ціна розкладу "Плюси / Мінуси"


async def charge_energy_for_plusminus(user_id: int, cost: int):
    """
    Перевірка та списання енергії для розкладу "Плюси / Мінуси".
    Повертає (ok, value):
      - ok == True  -> value = новий баланс
      - ok == False -> value = поточний баланс (нічого не списано)
    """
    current = await get_energy(user_id)
    if current < cost:
        return False, current

    await change_energy(user_id, -cost)
    return True, current - cost


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_PLUS_MINUS = """
Ти — досвідчений таролог.

Цей розклад називається "Плюси — Мінуси" і складається з двох карт:
1 — Плюси (переваги, можливості, сильні сторони ситуації)
2 — Мінуси (ризики, слабкі сторони, приховані проблеми)

Твоє завдання — допомогти людині зважити рішення.
Пиши українською або російською, як звертаються.

Структура відповіді:
1) 🔮 Підсумок (скоріше так / скоріше ні / нейтрально)
2) ➕ Плюси — розбір першої карти
3) ➖ Мінуси — розбір другої карти
4) 🌙 Рекомендація (як краще вчинити, на що звернути увагу)
"""


# ======================
#      FSM STATES
# ======================
class PlusMinusFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 2 КАРТ
# ======================
def combine_plus_minus_cards(paths, uprights, background="background.png") -> str:
    """
    Об'єднує 2 карти на PNG-фоні:
    - злегка обрізає поля
    - округлює кути
    - додає тінь
    - центрує 2 карти по центру
    Повертає шлях до тимчасового PNG.
    """

    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop_1mm(img: Image.Image) -> Image.Image:
        dpi = img.info.get("dpi", (300, 300))[0]
        px = int((1 * dpi) / 25.4)
        w, h = img.size
        if px <= 0 or px * 2 >= min(w, h):
            return img
        return img.crop((px, px, w - px, h - px))

    def round_corners(img: Image.Image, radius: int = 45) -> Image.Image:
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
        out = Image.new("RGBA", img.size)
        out.paste(img, (0, 0), mask)
        return out

    def add_shadow(
        img: Image.Image,
        offset=(12, 18),
        blur: int = 32,
        opacity: int = 160,
        radius: int = 45,
    ) -> Image.Image:
        w, h = img.size
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), radius, fill=opacity)
        shadow.paste((0, 0, 0, opacity), (0, 0), mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.alpha_composite(shadow, offset)
        layer.alpha_composite(img, (0, 0))
        return layer

    cards = []
    for path, up in zip(paths, uprights):
        img = Image.open(path).convert("RGBA")
        img = crop_1mm(img)
        if not up:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = add_shadow(img)
        cards.append(img)

    # Масштабування — карта займає ~26% ширини фону
    card_w = int(W * 0.26)
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)
    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    spacing = int(W * 0.05)  # проміжок між картами
    total_width = card_w * 2 + spacing
    start_x = (W - total_width) // 2
    y = (H - card_h) // 2

    positions = [start_x, start_x + card_w + spacing]

    for img, x in zip(cards, positions):
        bg.alpha_composite(img, (x, y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG")
    return temp.name


# ======================
#  GPT "ПЛЮСИ / МІНУСИ"
# ======================
async def interpret_plus_minus(question: str, cards_display: str) -> str:
    """
    cards_display:
    1. Назва карти (Плюси)
    2. Назва карти (Мінуси)
    """
    prompt = (
        f"{SYSTEM_PROMPT_PLUS_MINUS}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Карти розкладу:\n{cards_display}\n\n"
        "Дай глибокий, але зрозумілий розбір з урахуванням структури."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_PLUS_MINUS},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#       КНОПКА
# ======================
@plus_minus.message(F.text == "➕➖ Плюси / Мінуси")
async def plusminus_start(message: types.Message, state: FSMContext):
    """
    Старт: питаємо формулювати ситуацію / вибір.
    """
    await state.clear()
    await state.set_state(PlusMinusFSM.waiting_for_question)
    await message.answer(
        "❓ Сформулюй ситуацію або вибір, який хочеш зважити (плюси та мінуси).",
        reply_markup=ReplyKeyboardRemove(),
    )


# ======================
#       ПИТАННЯ
# ======================
@plus_minus.message(PlusMinusFSM.waiting_for_question)
async def plusminus_question(message: types.Message, state: FSMContext):
    question = (message.text or "").strip()
    if not question:
        await message.answer("Будь ласка, напиши питання текстом 🙏")
        return

    await state.update_data(question=question)

    # Інлайн-кнопки для обміну енергією або виходу в меню
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⚡ Обмінятись енергією ({ENERGY_COST_PLUS_MINUS}✨)",
                    callback_data="pm_pay",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в головне меню",
                    callback_data="pm_back",
                )
            ],
        ]
    )

    await message.answer(
        "✨ Чудово, питання прийнято.\n\n"
        "Щоб активувати розклад, треба обмінятись енергією з колодою ✨",
        reply_markup=kb,
    )

    await state.set_state(PlusMinusFSM.waiting_for_energy)


# ======================
#   ОБМІН ЕНЕРГІЄЮ / НАЗАД
# ======================
@plus_minus.callback_query(PlusMinusFSM.waiting_for_energy)
async def plusminus_energy_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # 🔙 Назад в меню
    if data == "pm_back":
        # Видаляємо повідомлення з кнопками
        try:
            await msg.delete()
        except Exception:
            pass

        kb = build_main_menu(user_id)
        await callback.message.bot.send_message(
            chat_id=msg.chat.id,
            text="🔙 Повертаю в головне меню.",
            reply_markup=kb,
        )

        await state.clear()
        await callback.answer()
        return

    if data != "pm_pay":
        await callback.answer()
        return

    await callback.answer()

    # 1) Перевірка та списання енергії
    ok, value = await charge_energy_for_plusminus(
        user_id,
        ENERGY_COST_PLUS_MINUS,
    )

    if not ok:
        current = value
        await msg.answer(
            "🔋 У вас недостатньо енергії для цього розкладу.\n"
            f"Потрібно: <b>{ENERGY_COST_PLUS_MINUS}</b> ✨\n"
            f"У вас є: <b>{current}</b> ✨",
            parse_mode="HTML",
            reply_markup=menu,
        )
        return

    # 2) Видаляємо попереднє повідомлення з кнопками
    try:
        await msg.delete()
    except Exception:
        pass

    # 3) Анімація обміну енергією (~2 сек)
    anim_msg = await callback.message.bot.send_message(
        chat_id=msg.chat.id,
        text="⚡ Обмінюємося енергією… ✨",
    )

    try:
        for i in range(4):  # 4 кроки по 0.5с = 2с
            bar = "✨" * (i + 1)
            try:
                await anim_msg.edit_text(f"⚡ Обмінюємося енергією… {bar}")
            except Exception:
                break
            await asyncio.sleep(0.5)
    except Exception:
        pass

    # 4) Ховаємо анімацію
    try:
        await anim_msg.delete()
    except Exception:
        pass

    # 5) Повідомлення про успішний обмін
    left = value
    await callback.message.bot.send_message(
        chat_id=msg.chat.id,
        text=(
            f"⚡ Обмін енергією успішний!\n"
            f"Ваша енергія: <b>{left}</b> ✨"
        ),
        parse_mode="HTML",
    )

    # 6) Показуємо кнопку WebApp для вибору 2 карт
    kb_reply = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                types.KeyboardButton(
                    text="✨ Обрати 2 карти",
                    web_app=types.WebAppInfo(
                        url="https://yuriy-vasylevsky.github.io/web2cards"
                    ),
                )
            ]
        ],
    )

    await callback.message.bot.send_message(
        chat_id=msg.chat.id,
        text="🃏 Тепер обери 2 карти через колоду нижче:",
        reply_markup=kb_reply,
    )

    await state.set_state(PlusMinusFSM.waiting_for_cards)


# ======================
#      КАРТИ З WEBAPP
# ======================
@plus_minus.message(PlusMinusFSM.waiting_for_cards, F.web_app_data)
async def plusminus_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] PLUS_MINUS WEBAPP:", data)

    action = data.get("action")
    # Підстрахуємось: приймаємо і "two_cards", і "three_cards", але очікуємо 2 карти
    if action not in ("two_cards", "three_cards"):
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 2:
        await message.answer("Для розкладу 'Плюси / Мінуси' потрібно саме 2 карти.")
        return

    state_data = await state.get_data()
    question = state_data.get("question")
    if not question:
        await message.answer("Щось пішло не так. Спробуй почати розклад заново.")
        await state.clear()
        return

    img_paths: list[str] = []
    uprights: list[bool] = []
    cards_display: list[str] = []

    # 1 — Плюси, 2 — Мінуси
    positions_label = ["(Плюси)", "(Мінуси)"]

    for i, card in enumerate(chosen, start=1):
        eng_name = card["name"]
        upright = card["upright"]

        info = TAROT_CARDS.get(eng_name)
        if not info:
            continue

        img_paths.append(info["image"])
        uprights.append(upright)

        ua = info["ua_name"]
        arrow = "⬆️" if upright else "⬇️"
        label = positions_label[i - 1]
        cards_display.append(f"{i}. {ua} {arrow} {label}")

    if len(img_paths) != 2:
        await message.answer("Не вдалося завантажити обидві карти.")
        await state.clear()
        return

    # 1️⃣ Комбінуємо 2 карти в одне зображення
    final_img = combine_plus_minus_cards(
        img_paths,
        uprights,
        background="background.png",  # твій фон
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Плюси / Мінуси",
    )

    # 2️⃣ Анімація "аналіз..."
    load = await message.answer("🔮 Аналіз ситуації…")

    async def anim():
        i = 0
        while True:
            try:
                await load.edit_text(
                    "🔮 Аналіз ситуації…\n" + "🔮" * ((i % 5) + 1)
                )
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    # 3️⃣ GPT
    try:
        interpretation = await interpret_plus_minus(
            question, "\n".join(cards_display)
        )
    finally:
        task.cancel()
        try:
            await load.delete()
        except Exception:
            pass

    # 4️⃣ Відповідь користувачу
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>➕➖ Розклад: Плюси / Мінуси</b>\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    try:
        os.remove(final_img)
    except Exception:
        pass

    await state.clear()

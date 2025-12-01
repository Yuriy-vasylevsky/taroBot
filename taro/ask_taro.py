import os
import json
import tempfile
import asyncio
from PIL import Image, ImageDraw, ImageFilter
from aiogram import Router, F, types
from aiogram.types import (
    FSInputFile,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from modules.menu import menu, popular_menu
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config
from modules.user_stats_db import get_energy, change_energy

ask_taro = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# ======================
#   НАЛАШТУВАННЯ ЕНЕРГІЇ
# ======================
ENERGY_COST_DIALOG_3CARDS = 3  # ціна цього розкладу

async def charge_energy_for_spread(user_id: int, cost: int):
    """
    Перевірка та списання енергії (без повідомлень в чат):
    Повертає (ok, value):
      - ok == True  -> value = новий баланс
      - ok == False -> value = поточний баланс (нічого не списано)
    """
    current = await get_energy(user_id)

    if current < cost:
        return False, current

    await change_energy(user_id, -cost)
    new_balance = current - cost
    return True, new_balance


# ======================
#     SYSTEM PROMPT
# ======================
SYSTEM_PROMPT = """
Ти — досвідчений таролог-наставник.
Говори глибоко, тепло, інтуїтивно.
Уникай мотлоху, пиши сильні, красиві смисли.
Дай відповідь українською або російською, як звертаються.
Структура:
1) 🔮 Підсумок
2) ✨ Короткий розбір карт
3) 🌙 Висновок
4) 💛 Мантра
"""


# ======================
#   FSM СТАНИ
# ======================
class TarotDialog(StatesGroup):
    choosing_layout = State()
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


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
            # якщо щось не вийшло (старе/відсутнє) — просто пропускаємо
            pass


# ======================
#   РОЗКЛАДИ (3 карти)
# ======================
THREE_CARD_LAYOUTS = {
    "layout_ptf": {
        "name": "Минуле — Теперішнє — Майбутнє",
        "positions": ["Минуле", "Теперішнє", "Майбутнє"],
    },
    "layout_pcr": {
        "name": "Проблема — Причина — Рішення",
        "positions": ["Проблема", "Причина", "Рішення"],
    },
    "layout_spr": {
        "name": "Ситуація — Порада — Результат",
        "positions": ["Ситуація", "Порада", "Результат"],
    },
}


# ======================
#   КОМБІНУВАТИ 3 КАРТИ + ФОН
# ======================
def combine_three_cards_with_background(
    paths, uprights, background_path: str = "background.png"
) -> str:
    """
    Об'єднує 3 карти на PNG-фоні:
    - трохи обрізає поля
    - округлює кути
    - додає 3D-тінь (ефект підняття)
    - ідеально центрує на фоні
    Повертає шлях до тимчасового PNG.
    """

    # --------- Завантажуємо фон ---------
    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size

    # Обрізання ~1 мм по контуру (якщо є DPI)
    def crop_1mm(img: Image.Image) -> Image.Image:
        dpi = img.info.get("dpi", (300, 300))[0]
        mm_to_px = dpi / 25.4
        px = int(1 * mm_to_px)
        w, h = img.size
        if px <= 0 or px * 2 >= min(w, h):
            return img
        return img.crop((px, px, w - px, h - px))

    # Заокруглення кутів
    def round_corners(img: Image.Image, radius: int = 45) -> Image.Image:
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
        rounded = Image.new("RGBA", img.size)
        rounded.paste(img, (0, 0), mask)
        return rounded

    # 3D-тінь
    def add_3d_shadow(
        img: Image.Image,
        offset=(12, 18),
        blur: int = 38,
        shadow_opacity: int = 140,
        corner_radius: int = 45,
    ) -> Image.Image:
        w, h = img.size

        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), corner_radius, fill=shadow_opacity)

        shadow.paste((0, 0, 0, shadow_opacity), (0, 0), mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.alpha_composite(shadow, offset)
        layer.alpha_composite(img, (0, 0))

        return layer

    # --------- Готуємо карти ---------
    cards = []
    for path, up in zip(paths, uprights):
        img = Image.open(path).convert("RGBA")
        img = crop_1mm(img)

        if not up:
            img = img.rotate(180, expand=True)

        img = round_corners(img)
        img = add_3d_shadow(img)
        cards.append(img)

    # --------- Масштабування ---------
    card_w = int(W * 0.27)
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)

    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    # --------- Центрування ---------
    spacing = int(W * 0.03)
    total_width = card_w * 3 + spacing * 2
    start_x = int((W - total_width) / 2)
    y = int((H - card_h) / 2)

    x_positions = [
        start_x,
        start_x + card_w + spacing,
        start_x + (card_w + spacing) * 2,
    ]

    for img, x in zip(cards, x_positions):
        bg.alpha_composite(img, (x, y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG", quality=95)
    return temp.name


# ======================
#     GPT ТЛУМАЧЕННЯ
# ======================
async def interpret_cards_gpt(
    question: str,
    cards_display: str,
    layout: dict,
) -> str:
    layout_block = (
        f"Обраний розклад:\n{layout['name']}\n"
        f"Позиції карт:\n"
        f"1 — {layout['positions'][0]}\n"
        f"2 — {layout['positions'][1]}\n"
        f"3 — {layout['positions'][2]}\n"
    )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"{layout_block}\n"
        f"Витягнуті карти:\n{cards_display}\n\n"
        f"Дай глибоке тлумачення строго відповідно до позицій цього розкладу."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#   СТАРТ: "Діалог з Таро"
# ======================
@ask_taro.message(F.text == "💬 Діалог з Таро")
async def tarot_dialog_start(message: types.Message, state: FSMContext):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🔮 Минуле — Теперішнє — Майбутнє",
                    callback_data="layout_ptf",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⚡ Проблема — Причина — Рішення",
                    callback_data="layout_pcr",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="✨ Ситуація — Порада — Результат",
                    callback_data="layout_spr",
                )
            ],
        ]
    )

    await state.clear()
    await state.set_state(TarotDialog.choosing_layout)

    # перше службове повідомлення діалогу
    msg = await message.answer("🔮 Обери тип розкладу:", reply_markup=kb)
    await state.update_data(dialog_msg_ids=[msg.message_id])


# ======================
#   ОБРАННЯ РОЗКЛАДУ
# ======================
@ask_taro.callback_query(TarotDialog.choosing_layout)
async def choose_layout(callback: types.CallbackQuery, state: FSMContext):
    layout_key = callback.data
    layout = THREE_CARD_LAYOUTS.get(layout_key)

    if not layout:
        await callback.answer("Невідомий розклад.", show_alert=True)
        return

    await state.update_data(layout=layout)

    msg2 = await callback.message.answer(
        f"🔮 Обрано розклад: <b>{layout['name']}</b>\n\n"
        "Тепер сформулюй своє питання до цього розкладу:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await remember_dialog_msg(state, msg2)

    await state.set_state(TarotDialog.waiting_for_question)
    await callback.answer()


# ======================
#   Питання користувача
# ======================
@ask_taro.message(TarotDialog.waiting_for_question)
async def tarot_dialog_question(message: types.Message, state: FSMContext):
    question = (message.text or "").strip()
    if not question:
        await message.answer("Будь ласка, сформулюй питання текстом.")
        return

    await state.update_data(question=question)

    # Інлайн-кнопки "обмінятись енергією" + "назад в меню розкладів"
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⚡ Обмінятись енергією ({ENERGY_COST_DIALOG_3CARDS}✨)",
                    callback_data="dialog3_pay",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню розкладів",
                    callback_data="dialog3_back",
                )
            ],
        ]
    )

    msg3 = await message.answer(
        "✨ Чудово, питання прийнято.\n\n"
        f"Щоб активувати розклад потрібно <b>«Обмінятись енергією» з колодою</b>.\n\n"
        f"✨Сфокусуйтесь на своєму питанні✨\n",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await remember_dialog_msg(state, msg3)

    await state.set_state(TarotDialog.waiting_for_energy)


# ======================
#   ОБМІН ЕНЕРГІЄЮ / НАЗАД
# ======================
@ask_taro.callback_query(TarotDialog.waiting_for_energy)
async def tarot_energy_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # 🔙 Назад в меню розкладів
    if data == "dialog3_back":
        # видаляємо всі службові повідомлення діалогу (вибір розкладу, підтвердження тощо)
        await clear_dialog_messages(
            state=state,
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
        )

        # показуємо меню популярних розкладів
        await callback.message.bot.send_message(
            chat_id=callback.message.chat.id,
            text="📚 Повертаю в меню популярних розкладів.",
            reply_markup=popular_menu,
        )

        await state.clear()
        await callback.answer()
        return

    # Якщо це не оплата — ігноруємо
    if data != "dialog3_pay":
        await callback.answer()
        return

    await callback.answer()

    # 1) Перевіряємо та списуємо енергію
    ok, value = await charge_energy_for_spread(
        user_id,
        ENERGY_COST_DIALOG_3CARDS,
    )

    if not ok:
        current = value
        await msg.answer(
            "🔋 У вас зараз недостатньо енергії для цього розкладу.\n"
            f"Потрібно: <b>{ENERGY_COST_DIALOG_3CARDS}</b> ✨\n"
            f"У вас є: <b>{current}</b> ✨\n\n",
            parse_mode="HTML",
            reply_markup=menu,
        )
        return

    # 2) Видаляємо попереднє повідомлення з кнопками
    try:
        await msg.delete()
    except Exception:
        pass

    # 3) Анімація "обміну енергією" (≈2 сек)
    anim_msg = await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text="⚡ Обмінюємося енергією з колодою… ✨",
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

    # 5) Повідомлення "обмін успішний"
    left = value
    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text=(
            f"⚡ Обмін енергією успішний!\n"
            f"Ваша енергія: <b>{left}</b> ✨"
        ),
        parse_mode="HTML",
    )

    # 6) Показуємо кнопку WebApp для вибору 3 карт
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

    await state.set_state(TarotDialog.waiting_for_cards)


# ======================
#   3 КАРТИ з WebApp
# ======================
@ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
async def tarot_dialog_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] DIALOG WEBAPP:", data)

    if data.get("action") != "three_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 3:
        await message.answer("Для цього розкладу потрібно саме 3 карти.")
        return

    state_data = await state.get_data()
    question = state_data.get("question")
    layout = state_data.get("layout")

    if not question or not layout:
        await message.answer("Щось пішло не так. Спробуй почати діалог заново.")
        await state.clear()
        return

    img_paths: list[str] = []
    uprights: list[bool] = []
    cards_display: list[str] = []

    for i, card in enumerate(chosen, start=1):
        eng = card["name"]
        up = card["upright"]

        info = TAROT_CARDS.get(eng)
        if not info:
            continue

        img_paths.append(info["image"])
        uprights.append(up)

        ua = info["ua_name"]
        arrow = "⬆️" if up else "⬇️"
        cards_display.append(f"{i}. {ua} {arrow}")

    if len(img_paths) != 3:
        await message.answer("Не вдалося завантажити всі три карти.")
        await state.clear()
        return

    # 1️⃣ Комбінуємо 3 карти в одне зображення
    final_img = combine_three_cards_with_background(
        img_paths,
        uprights,
        background_path="background.png",  # твій PNG-фон
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption=f"🔮 Розклад: {layout['name']}",
    )

    # 2️⃣ Анімація "тлумачення…"
    load_msg = await message.answer("🔮 Тлумачення…")

    async def anim():
        i = 0
        while True:
            try:
                await load_msg.edit_text(
                    "🔮 Тлумачення…\n" + "🔮" * ((i % 5) + 1)
                )
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    anim_task = asyncio.create_task(anim())

    # 3️⃣ GPT інтерпретація
    try:
        text = await interpret_cards_gpt(
            question,
            "\n".join(cards_display),
            layout,
        )
    finally:
        anim_task.cancel()
        try:
            await load_msg.delete()
        except Exception:
            pass

    # 4️⃣ Відповідь користувачу
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>🔮 Розклад:</b> {layout['name']}\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{text}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    # Чистимо тимчасовий файл
    try:
        os.remove(final_img)
    except Exception:
        pass

    await state.clear()

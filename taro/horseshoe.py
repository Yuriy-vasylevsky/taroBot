
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
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config

from modules.user_stats_db import get_energy, change_energy


horseshoe = Router()
client = AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)


# ======================
#   ENERGY CONFIG
# ======================
ENERGY_COST_HORSESHOE = 5


async def charge_energy_horseshoe(user_id: int, cost: int):
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
SYSTEM_PROMPT_HORSESHOE = """
Ти — досвідчений таролог-наставник.

Розклад "Підкова" (7 карт) має такі позиції:
1 — Минуле
2 — Теперішнє
3 — Майбутнє
4 — Приховане
5 — Порада
6 — Зовнішній вплив
7 — Потенційний результат

Структура відповіді:
1) 🕰 Минуле
2) 🎯 Теперішнє
3) 🔮 Майбутнє
4) 👁️ Приховане
5) 🧭 Порада
6) 🌐 Зовнішній вплив
7) ⭐ Потенційний результат
8) 💛 Ключове послання розкладу
"""


# ======================
#      FSM STATES
# ======================
class HorseshoeFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


# ======================
#   IMAGE BUILDER (7 карт)
# ======================
def combine_horseshoe_cards(paths, uprights, background="background.png") -> str:
    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop(img):
        dpi = img.info.get("dpi", (300, 300))[0]
        px = int((1 * dpi) / 25.4)
        return img.crop((px, px, img.size[0] - px, img.size[1] - px))

    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, *img.size], radius, fill=255)
        out = Image.new("RGBA", img.size)
        out.paste(img, mask=mask)
        return out

    def shadow(img, offset=(12, 18), blur=30):
        w, h = img.size
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]))
        layer.paste(sh, offset, sh)
        layer.paste(img, (0, 0), img)
        return layer

    cards = []
    for p, u in zip(paths, uprights):
        img = Image.open(p).convert("RGBA")
        img = crop(img)
        if not u:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = shadow(img)
        cards.append(img)

    card_w = int(W * 0.15)
    ratio = card_w / cards[0].width
    card_h = int(cards[0].height * ratio)

    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    # Позиції карт у формі підкови (як на зразку)
    # 1 - ліворуч знизу
    # 2 - ліворуч середина
    # 3 - ліворуч вгорі
    # 4 - центр вгорі
    # 5 - праворуч вгорі
    # 6 - праворуч середина
    # 7 - праворуч знизу
    positions = [
        (int(W * 0.08), int(H * 0.62)),  # 1 - ліворуч знизу
        (int(W * 0.18), int(H * 0.42)),  # 2 - ліворуч середина
        (int(W * 0.30), int(H * 0.22)),  # 3 - ліворуч вгорі
        (int(W * 0.425), int(H * 0.10)),  # 4 - центр вгорі
        (int(W * 0.55), int(H * 0.22)),  # 5 - праворуч вгорі
        (int(W * 0.67), int(H * 0.42)),  # 6 - праворуч середина
        (int(W * 0.77), int(H * 0.62)),  # 7 - праворуч знизу
    ]

    for img, (x, y) in zip(cards, positions):
        bg.alpha_composite(img, (x, y))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(tmp.name)
    return tmp.name


# ======================
#   GPT INTERPRETATION
# ======================
async def interpret_horseshoe(question: str, cards_display: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT_HORSESHOE}\n\n"
        f"Питання: {question}\n\n"
        f"Карти:\n{cards_display}\n\n"
        f"Дай глибоке тлумачення."
    )

    resp = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_HORSESHOE},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#   КНОПКА "НАЗАД" ДЛЯ HORSESHOE
# ======================
def build_back_horseshoe_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню розкладів",
                    callback_data="hs_back_start",
                )
            ]
        ]
    )


# ======================
#       КНОПКА СТАРТ
# ======================
@horseshoe.message(F.text == "🍀 Підкова (7 карт)")
async def horseshoe_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(HorseshoeFSM.waiting_for_question)

    # 1) просимо ввести питання і прибираємо reply-клавіатуру
    msg = await message.answer(
        "❓ Сформулюй питання для розкладу «Підкова» (7 карт).",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.update_data(dialog_msg_ids=[msg.message_id])

    # 2) окремим повідомленням – інлайн "назад"
    msg_back = await message.answer(
        "💬",
        reply_markup=build_back_horseshoe_kb(),
    )
    await remember_dialog_msg(state, msg_back)


# ======================
#   НАЗАД ПІД ЧАС ВВОДУ ПИТАННЯ
# ======================
@horseshoe.callback_query(HorseshoeFSM.waiting_for_question, F.data == "hs_back_start")
async def horseshoe_back_from_question(
    callback: types.CallbackQuery, state: FSMContext
):
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
@horseshoe.message(HorseshoeFSM.waiting_for_question)
async def horseshoe_question(message: types.Message, state: FSMContext):
    q = (message.text or "").strip()
    if not q:
        await message.answer("Напиши питання 🙏")
        return

    await state.update_data(question=q)

    # кнопки обміну енергією
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⚡ Обмінятись енергією ({ENERGY_COST_HORSESHOE}✨)",
                    callback_data="hs_pay",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню",
                    callback_data="hs_back",
                )
            ],
        ]
    )

    msg = await message.answer(
        "✨Сфокусуйтесь на своєму питанні та обміняйтесь енергією✨\n",
        reply_markup=kb,
    )
    await remember_dialog_msg(state, msg)

    await state.set_state(HorseshoeFSM.waiting_for_energy)


# ======================
#   ОПЛАТА ЕНЕРГІЄЮ
# ======================
@horseshoe.callback_query(HorseshoeFSM.waiting_for_energy)
async def horseshoe_energy(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # 🔙 Назад в меню
    if data == "hs_back":
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

    if data != "hs_pay":
        await callback.answer()
        return

    await callback.answer()

    # Перевірка та списання енергії
    ok, value = await charge_energy_horseshoe(user_id, ENERGY_COST_HORSESHOE)

    if not ok:
        current = value
        need = ENERGY_COST_HORSESHOE
        user = callback.from_user

        await msg.answer(
            f"🔋 <b>Енергія закінчилась</b> — щоб зробити розклад, потрібно поповнити ⚡\n\n"
            f"Обери дію:",
            parse_mode="HTML",
            reply_markup=build_no_energy_kb(),
        )

        # Очищаємо стан після показу помилки
        await state.clear()
        return

    # Видаляємо попереднє повідомлення з кнопками
    try:
        await msg.delete()
    except Exception:
        pass

    # Анімація обміну енергією
    anim_msg = await callback.message.bot.send_message(
        msg.chat.id,
        text="⚡ Обмінюємося енергією з колодою… ✨",
    )

    try:
        for i in range(4):
            bar = "✨" * (i + 1)
            try:
                await anim_msg.edit_text(f"⚡ Обмінюємося енергією… {bar}")
            except Exception:
                break
            await asyncio.sleep(0.3)
    except Exception:
        pass

    # Ховаємо анімацію
    try:
        await anim_msg.delete()
    except Exception:
        pass

    # Повідомлення про успішний обмін
    left = value
    await callback.message.bot.send_message(
        msg.chat.id,
        text=(f"⚡ Обмін енергією успішний!\n" f"Ваша енергія: <b>{left}</b> ✨"),
        parse_mode="HTML",
    )

    # Показуємо кнопку WebApp для вибору 7 карт + кнопку повернутись в меню
    kb_reply = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                types.KeyboardButton(
                    text="✨ Обрати 7 карт",
                    web_app=types.WebAppInfo(
                        url="https://yuriy-vasylevsky.github.io/web7cards"
                    ),
                )
            ]
        ],
    )

    await callback.message.bot.send_message(
        msg.chat.id,
        text="🃏 Тепер оберіть 7 карт через колоду нижче:",
        reply_markup=kb_reply,
    )

    await state.set_state(HorseshoeFSM.waiting_for_cards)


# ======================
#      WEBAPP CARDS
# ======================
@horseshoe.message(HorseshoeFSM.waiting_for_cards, F.web_app_data)
async def horseshoe_cards(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        await message.answer(
            "Не вдалося прочитати дані з колоди. Спробуй ще раз.",
            reply_markup=popular_menu,
        )
        await state.clear()
        return

    if data.get("action") != "seven_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 7:
        await message.answer("Потрібно саме 7 карт 🙏", reply_markup=popular_menu)
        await state.clear()
        return

    state_data = await state.get_data()
    question = state_data.get("question")

    if not question:
        await message.answer(
            "Щось пішло не так. Спробуй почати розклад заново.",
            reply_markup=popular_menu,
        )
        await state.clear()
        return

    img_paths = []
    uprights = []
    cards_display = []

    labels = [
        "Минуле",
        "Теперішнє",
        "Майбутнє",
        "Приховане",
        "Порада",
        "Зовнішній вплив",
        "Потенційний результат",
    ]

    for i, card in enumerate(chosen, start=1):
        name = card.get("name")
        up = bool(card.get("upright", True))

        info = TAROT_CARDS.get(name)
        if not info:
            continue

        img_paths.append(info["image"])
        uprights.append(up)

        ua = info["ua_name"]
        arrow = "⬆️" if up else "⬇️"
        cards_display.append(f"{i}. {ua} {arrow} — {labels[i-1]}")

    if len(img_paths) != 7:
        await message.answer(
            "Не вдалося завантажити всі карти.", reply_markup=popular_menu
        )
        await state.clear()
        return

    # Комбінуємо 7 карт в одне зображення
    final_img = combine_horseshoe_cards(img_paths, uprights)

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Підкова",
    )

    # Анімація "тлумачення…"
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

    # GPT інтерпретація
    try:
        interpretation = await interpret_horseshoe(question, "\n".join(cards_display))
    finally:
        anim_task.cancel()
        try:
            await load_msg.delete()
        except Exception:
            pass

    # Відповідь користувачу
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>🍀 Розклад Підкова:</b>\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=popular_menu,
    )

    # Чистимо тимчасовий файл
    try:
        os.remove(final_img)
    except Exception:
        pass

    await state.clear()



import os
import json
import tempfile
import asyncio

from aiogram import Router, F, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from PIL import Image, ImageDraw, ImageFilter

from modules.menu import menu
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config


you_other = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_YOU_OTHER = """
Ти — досвідчений таролог-психолог.

Розклад "Ти — Інша людина" складається з 2 карт:
1 — Ти (емоції, наміри, очікування, внутрішній стан)
2 — Інша людина (її емоції, наміри, очікування, внутрішній стан)

Твоє завдання — допомогти людині зрозуміти динаміку між ними:
де взаємність, де напруга, де нерівновага, де надія.

Пиши українською або російською, як звертаються.
Структура відповіді:
1) 🔮 Динаміка між вами (короткий підсумок)
2) 🧩 Ти — розбір першої карти (що ти відчуваєш, як виглядаєш у цій ситуації)
3) 🧩 Інша людина — розбір другої карти (що відчуває вона/він, як бачить ситуацію)
4) 🌙 Висновок (що між вами зараз, куди це може рухатися)
5) 💛 Порада (як краще поводитись, на що звернути увагу, що може покращити контакт)
"""


# ======================
#      FSM STATES
# ======================
class YouOtherFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 2 КАРТ
# ======================
def combine_you_other_cards(paths, uprights, background: str = "background.png") -> str:
    """
    Об'єднує 2 карти на PNG-фоні:
    - трохи обрізає поля
    - округлює кути
    - додає тінь (ефект "піднятої" карти)
    - центрує 2 карти по центру стола
    Повертає шлях до тимчасового PNG-файлу.
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

    # Масштаб: ~26% ширини фону
    card_w = int(W * 0.26)
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)
    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    spacing = int(W * 0.05)
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
#  GPT "ТИ / ІНША ЛЮДИНА"
# ======================
async def interpret_you_other(question: str, cards_display: str) -> str:
    """
    cards_display:
    1. ... (Ти)
    2. ... (Інша людина)
    """
    prompt = (
        f"{SYSTEM_PROMPT_YOU_OTHER}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Карти розкладу:\n{cards_display}\n\n"
        "Опиши щиро, емпатійно, з фокусом на почуттях та динаміці між людьми."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_YOU_OTHER},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#       КНОПКА
# ======================
@you_other.message(F.text == "👥 Ти / Інша людина")
async def youother_start(message: types.Message, state: FSMContext):
    """
    Старт розкладу: питаємо про стосунок / ситуацію між двома людьми.
    """
    await state.set_state(YouOtherFSM.waiting_for_question)
    await message.answer(
        "❓ Розкажи, про які стосунки або ситуацію між тобою та іншою людиною ти хочеш дізнатися.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ======================
#       ПИТАННЯ
# ======================
@you_other.message(YouOtherFSM.waiting_for_question)
async def youother_question(message: types.Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("Будь ласка, напиши питання текстом 🙏")
        return

    await state.update_data(question=question)

    kb = types.ReplyKeyboardMarkup(
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

    await message.answer(
        "🃏 Тепер обери 2 карти через колоду нижче:", reply_markup=kb
    )
    await state.set_state(YouOtherFSM.waiting_for_cards)


# ======================
#      КАРТИ З WEBAPP
# ======================
@you_other.message(YouOtherFSM.waiting_for_cards, F.web_app_data)
async def youother_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] YOU_OTHER WEBAPP:", data)

    action = data.get("action")
    if action not in ("two_cards", "three_cards"):
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 2:
        await message.answer("Для розкладу 'Ти — Інша людина' потрібно саме 2 карти.")
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

    # 1 — Ти, 2 — Інша людина
    positions_label = ["(Ти)", "(Інша людина)"]

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
    final_img = combine_you_other_cards(
        img_paths,
        uprights,
        background="background.png",  # твій фон "таро-стіл"
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Ти — Інша людина",
    )

    # 2️⃣ Анімація "аналіз..."
    load = await message.answer("🔮 Читаю, що між вами…")

    async def anim():
        i = 0
        while True:
            try:
                await load.edit_text(
                    "🔮 Читаю, що між вами…\n" + "🔮" * ((i % 5) + 1)
                )
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    # 3️⃣ GPT
    try:
        interpretation = await interpret_you_other(
            question, "\n".join(cards_display)
        )
    finally:
        task.cancel()
        try:
            await load.delete()
        except Exception:
            pass

    # 4️⃣ Відповідь юзеру
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>👥 Розклад: Ти — Інша людина</b>\n"
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

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


horseshoe = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_HORSESHOE = """
Ти — досвідчений таролог-наставник.

Розклад "Підкова" (7 карт) має такі позиції:
1 — Минуле (що привело до теперішньої ситуації)
2 — Теперішнє (основна енергія моменту)
3 — Майбутнє (ймовірний напрям розвитку подій)
4 — Приховане (те, що не видно, тіньові впливи, несвідоме)
5 — Порада (як краще діяти, куди спрямувати енергію)
6 — Зовнішній вплив (люди, обставини, система, середовище)
7 — Потенційний результат (чим це може завершитися при поточному курсі)

Твоє завдання — дати людині глибоке, але зрозуміле бачення ситуації.

Пиши українською або російською, як до тебе звертаються.
Структура відповіді:

1) 🕰 Минуле
2) 🎯 Теперішнє
3) 🔮 Майбутнє
4) 👁️ Приховане
5) 🧭 Порада
6) 🌐 Зовнішній вплив
7) ⭐ Потенційний результат
8) 💛 Ключове послання розкладу (1–3 речення, короткий висновок)
"""


# ======================
#      FSM STATES
# ======================
class HorseshoeFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 7 КАРТ (ПІДКОВА)
# ======================
def combine_horseshoe_cards(paths, uprights, background: str = "background.png") -> str:
    """
    Об'єднує 7 карт на PNG-фоні в формі підкови.
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
        blur: int = 30,
        opacity: int = 150,
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

    # Масштаб: трохи менші, щоб 7 карт комфортно влізли
    card_w = int(W * 0.16)
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)
    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    # Позиції в формі підкови (x, y) як частки від W, H
    positions = [
        (int(W * 0.18), int(H * 0.60)),  # 1 — низ зліва
        (int(W * 0.12), int(H * 0.40)),  # 2 — середина зліва
        (int(W * 0.28), int(H * 0.22)),  # 3 — верх зліва
        (int(W * 0.50), int(H * 0.18)),  # 4 — верх по центру
        (int(W * 0.72), int(H * 0.22)),  # 5 — верх справа
        (int(W * 0.84), int(H * 0.42)),  # 6 — середина справа
        (int(W * 0.50), int(H * 0.62)),  # 7 — низ по центру
    ]

    for img, (x, y) in zip(cards, positions):
        bg.alpha_composite(img, (x, y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG")
    return temp.name


# ======================
#  GPT "ПІДКОВА"
# ======================
async def interpret_horseshoe(question: str, cards_display: str) -> str:
    """
    cards_display — список карт з позиціями (1–7).
    """
    prompt = (
        f"{SYSTEM_PROMPT_HORSESHOE}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Карти розкладу:\n{cards_display}\n\n"
        "Дотримуйся структури та пиши чесно, емпатійно, без банальних фраз."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_HORSESHOE},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1100,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#       КНОПКА
# ======================
@horseshoe.message(F.text == "🍀 Підкова (7 карт)")
async def horseshoe_start(message: types.Message, state: FSMContext):
    """
    Старт розкладу "Підкова".
    """
    await state.set_state(HorseshoeFSM.waiting_for_question)
    await message.answer(
        "❓ Сформулюй ситуацію або питання, яке хочеш розглянути в розкладі «Підкова» (7 карт).",
        reply_markup=ReplyKeyboardRemove(),
    )


# ======================
#       ПИТАННЯ
# ======================
@horseshoe.message(HorseshoeFSM.waiting_for_question)
async def horseshoe_question(message: types.Message, state: FSMContext):
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
                    text="✨ Обрати 7 карт",
                    web_app=types.WebAppInfo(
                        # 🔗 Постав тут свій URL WebApp-а на 7 карт
                        url="https://yuriy-vasylevsky.github.io/web7cards"
                    ),
                )
            ]
        ],
    )

    await message.answer(
        "🃏 Тепер обери 7 карт через інтерактивну колоду:", reply_markup=kb
    )
    await state.set_state(HorseshoeFSM.waiting_for_cards)


# ======================
#      КАРТИ З WEBAPP
# ======================
@horseshoe.message(HorseshoeFSM.waiting_for_cards, F.web_app_data)
async def horseshoe_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] HORSESHOE WEBAPP:", data)

    action = data.get("action")
    if action != "seven_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 7:
        await message.answer("Для розкладу «Підкова» потрібно саме 7 карт.")
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

    position_names = [
        "Минуле",
        "Теперішнє",
        "Майбутнє",
        "Приховане",
        "Порада",
        "Зовнішній вплив",
        "Потенційний результат",
    ]

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
        pos_name = position_names[i - 1]
        cards_display.append(f"{i}. {ua} {arrow} — {pos_name}")

    if len(img_paths) != 7:
        await message.answer("Не вдалося завантажити всі 7 карт.")
        await state.clear()
        return

    # 1️⃣ Комбінуємо 7 карт в одне зображення (форма підкови)
    final_img = combine_horseshoe_cards(
        img_paths,
        uprights,
        background="background.png",  # тут твій фон-стіл
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Підкова (7 карт)",
    )

    # 2️⃣ Анімація "читаю..."
    load = await message.answer("🔮 Читаю твій розклад «Підкова»…")

    async def anim():
        i = 0
        while True:
            try:
                await load.edit_text(
                    "🔮 Читаю твій розклад «Підкова»…\n" + "🔮" * ((i % 5) + 1)
                )
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    # 3️⃣ GPT-інтерпретація
    try:
        interpretation = await interpret_horseshoe(
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
        f"<b>🍀 Розклад: Підкова (7 карт)</b>\n"
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

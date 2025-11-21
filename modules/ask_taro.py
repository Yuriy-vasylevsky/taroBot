import os
import json
import tempfile
from PIL import Image
from aiogram import Router, types, F
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from modules.menu import menu
from cards_data import TAROT_CARDS

from openai import AsyncOpenAI
import config

ask_taro = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


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
    waiting_for_question = State()
    waiting_for_cards = State()



def combine_three_cards_with_background(paths, uprights, background_path="background.png"):
    """
    Об'єднує 3 карти на PNG-фоні:
    - обрізає 4 мм
    - округлює кути
    - додає 3D-тінь (ефект підняття)
    - ідеально центрує
    """

    import tempfile
    from PIL import Image, ImageDraw, ImageFilter

    # --------- Завантажуємо фон ---------
    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size

    # Обрізання 4 мм
    def crop_4mm(img):
        dpi = img.info.get('dpi', (300,300))[0]
        mm_to_px = dpi / 25.4
        px = int(1 * mm_to_px)
        w, h = img.size
        return img.crop((px, px, w - px, h - px))

    # Заокруглення кутів
    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
        rounded = Image.new("RGBA", img.size)
        rounded.paste(img, (0, 0), mask)
        return rounded

    # 3D EFFECT — м’яка тінь
    def add_3d_shadow(img, offset=(12, 18), blur=38, shadow_opacity=140):
        w, h = img.size

        # тінь як чорний силует
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), 45, fill=shadow_opacity)

        shadow.paste((0, 0, 0, shadow_opacity), (0, 0), mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        # новий холст з тінню
        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.alpha_composite(shadow, offset)
        layer.alpha_composite(img, (0, 0))

        return layer

    # --------- Готуємо карти ---------
    cards = []
    for path, up in zip(paths, uprights):
        img = Image.open(path).convert("RGBA")
        img = crop_4mm(img)

        if not up:
            img = img.rotate(180, expand=True)

        img = round_corners(img)
        img = add_3d_shadow(img)  # ← ЕФЕКТ ПІДНЯТТЯ

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
        start_x + (card_w + spacing) * 2
    ]

    # --------- Накладаємо ---------
    for img, x in zip(cards, x_positions):
        bg.alpha_composite(img, (x, y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG", quality=95)

    return temp.name

# ======================
#     GPT ТЛУМАЧЕННЯ
# ======================
async def interpret_cards_gpt(question: str, cards_display: str):
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Витягнуті карти:\n{cards_display}\n\n"
        f"Дай глибоке тлумачення:"
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_tokens=600,
        temperature=0.9
    )

    return resp.choices[0].message.content


# ======================
#     START: Діалог
# ======================
@ask_taro.message(lambda msg: msg.text == "💬 Діалог з Таро")
async def tarot_dialog_start(message: types.Message, state: FSMContext):
    await message.answer("🔮 Задай своє питання Таро...", reply_markup=ReplyKeyboardRemove())
    await state.set_state(TarotDialog.waiting_for_question)


# ======================
#   Після питання → WebApp
# ======================
@ask_taro.message(TarotDialog.waiting_for_question)
async def tarot_dialog_question(message: types.Message, state: FSMContext):
    question = message.text
    await state.update_data(question=question)

    kb = types.ReplyKeyboardMarkup(
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

    await message.answer("🃏 Обери 3 карти:", reply_markup=kb)
    await state.set_state(TarotDialog.waiting_for_cards)


# ======================
#       3 карти з WebApp
# ======================
@ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
async def tarot_dialog_cards(message: types.Message, state: FSMContext):

    data = json.loads(message.web_app_data.data)
    print("[DEBUG] DIALOG WEBAPP:", data)

    if data.get("action") != "three_cards":
        return

    chosen = data["chosen"]
    question = (await state.get_data())["question"]

    img_paths = []
    uprights = []
    cards_display = []

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

    # ======================
    # 1️⃣ Об’єднане фото
    # ======================
    final_img = combine_three_cards_with_background(
        img_paths,
        uprights,
        background_path="background.png"  # <-- ТВОЄ PNG
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Твій розклад"
    )

    # ======================
    # 2️⃣ Анімація
    # ======================
    load_msg = await message.answer("🔮 Тлумачення…")

    async def anim():
        i = 0
        while True:
            try:
                await load_msg.edit_text("🔮 Тлумачення…\n" + "🔮" * ((i % 5) + 1))
            except:
                break
            i += 1
            await asyncio.sleep(0.25)

    anim_task = asyncio.create_task(anim())

    # ======================
    # 3️⃣ GPT інтерпретація
    # ======================
    text = await interpret_cards_gpt(question, "\n".join(cards_display))

    anim_task.cancel()
    try: await load_msg.delete()
    except: pass

    # ======================
    # 4️⃣ Відправляємо результат
    # ======================
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{text}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    # Чистимо файл
    try: os.remove(final_img)
    except: pass

    await state.clear()

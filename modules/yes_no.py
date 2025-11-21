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


yes_no = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_YESNO = """
Ти — досвідчений таролог.
Твоє завдання — дати чітку відповідь: Так / Скоріше так / Нейтрально / Скоріше ні / Ні.
Поясни це на основі трьох карт, враховуючи:

1 — Основна енергія ситуації
2 — Прихована причина або вплив
3 — Імовірний результат

Структура відповіді:
1) 🔮 Підсумок (Так / Скоріше так / Нейтрально / Скоріше ні / Ні)
2) ✨ Короткий розбір кожної карти
3) 🌙 Висновок
"""


# ======================
#      FSM STATES
# ======================
class YesNoFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 3 КАРТ
# ======================
def combine_yesno_cards(paths, uprights, background="background.png"):

    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop(img):
        dpi = img.info.get("dpi", (300,300))[0]
        px = int((1 * dpi) / 25.4)
        return img.crop((px, px, img.size[0]-px, img.size[1]-px))

    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0,0,img.size[0],img.size[1]], radius, fill=255)
        result = Image.new("RGBA", img.size)
        result.paste(img, mask=mask)
        return result

    def add_shadow(img, offset=(12,18), blur=38):
        w,h=img.size
        shadow = Image.new("RGBA",(w,h),(0,0,0,180))
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w+offset[0],h+offset[1]), (0,0,0,0))
        layer.paste(shadow, offset, shadow)
        layer.paste(img, (0,0), img)
        return layer

    cards = []
    for p,u in zip(paths,uprights):
        img = Image.open(p).convert("RGBA")
        img = crop(img)
        if not u:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = add_shadow(img)
        cards.append(img)

    # scale
    cw = int(W*0.27)
    ratio = cw/cards[0].size[0]
    ch = int(cards[0].size[1]*ratio)
    cards=[c.resize((cw, int(ch*1.05)), Image.LANCZOS) for c in cards]

    spacing = int(W*0.03)
    total_width = cw*3 + spacing*2
    start_x = (W-total_width)//2
    y = (H-ch)//2

    for i,c in enumerate(cards):
        bg.alpha_composite(c,(start_x+i*(cw+spacing),y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG")
    return temp.name


# ======================
#  GPT ТЛУМАЧЕННЯ YES/NO
# ======================
async def interpret_yes_no(question: str, cards_display: str):
    prompt = (
        f"{SYSTEM_PROMPT_YESNO}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Карти:\n{cards_display}\n\n"
        "Зроби чіткий висновок Так / Скоріше так / Нейтрально / Скоріше ні / Ні."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_YESNO},
            {"role": "user", "content": prompt},
        ],
        max_tokens=700,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#       КНОПКА
# ======================
@yes_no.message(F.text == "✅ Так / Ні")
async def yesno_start(message: types.Message, state: FSMContext):
    await state.set_state(YesNoFSM.waiting_for_question)
    await message.answer(
        "❓ Задай питання, на яке хочеш отримати відповідь Так / Ні",
        reply_markup=ReplyKeyboardRemove()
    )


# ======================
#       ПИТАННЯ
# ======================
@yes_no.message(YesNoFSM.waiting_for_question)
async def yesno_question(message: types.Message, state: FSMContext):
    question = message.text.strip()
    await state.update_data(question=question)

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[ types.KeyboardButton(
            text="✨ Обрати 3 карти",
            web_app=types.WebAppInfo(url="https://yuriy-vasylevsky.github.io/tarodayweb")
        )]]
    )

    await message.answer("🃏 Обери 3 карти:", reply_markup=kb)
    await state.set_state(YesNoFSM.waiting_for_cards)


# ======================
#      КАРТИ З WEBAPP
# ======================
@yes_no.message(YesNoFSM.waiting_for_cards, F.web_app_data)
async def yesno_cards(message: types.Message, state: FSMContext):

    data = json.loads(message.web_app_data.data)
    if data.get("action") != "three_cards":
        return

    chosen = data["chosen"]
    question = (await state.get_data())["question"]

    img_paths=[]
    uprights=[]
    cards_display=[]

    for i,card in enumerate(chosen,start=1):
        info = TAROT_CARDS.get(card["name"])
        img_paths.append(info["image"])
        uprights.append(card["upright"])
        arrow="⬆️" if card["upright"] else "⬇️"
        cards_display.append(f"{i}. {info['ua_name']} {arrow}")

    final_img = combine_yesno_cards(img_paths, uprights)

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Так / Ні"
    )

    # loading anim
    load = await message.answer("🔮 Аналіз…")
    async def anim():
        i=0
        while True:
            try:
                await load.edit_text("🔮 Аналіз…\n" + "🔮"*((i%5)+1))
            except:
                break
            i+=1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    # GPT
    try:
        interpretation = await interpret_yes_no(question, "\n".join(cards_display))
    finally:
        task.cancel()
        try: await load.delete()
        except: pass

    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=menu
    )

    try: os.remove(final_img)
    except: pass

    await state.clear()

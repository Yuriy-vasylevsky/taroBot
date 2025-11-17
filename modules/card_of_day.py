
import json
import asyncio
from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from modules.menu import menu
from PIL import Image
import io
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config


card_router = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

WEBAPP_URL = "https://yuriy-vasylevsky.github.io/tarot-webapp/"


def load_card_image(path: str, upright: bool):
    """Створює BytesIO з перевернутою/прямою карткою."""
    img = Image.open(path)
    if not upright:
        img = img.rotate(180, expand=True)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


# ======================
# SYSTEM PROMPT GPT
# ======================
SYSTEM_PROMPT = """
Ти — досвідчений містичний таролог-наставник.
Відповідай українською мовою.
Будь теплим, інтуїтивним, але чітким і структурованим.

Структура відповіді:
1) 🔮 Ключова тема дня
2) ✨ Енергія дня
3) 💡 Порада
4) ⚠️ Чого уникати
5) 💛 Мантра дня

Пиши образно, красиво, але без зайвої "езотеричної води".
"""


async def interpret_card(display_name: str):
    """Отримує тлумачення карти напряму від GPT."""
    prompt = f"Карта дня: {display_name}\nДай тлумачення згідно структури."

    completion = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=450,
        temperature=0.9
    )

    return completion.choices[0].message.content


# ===============================
#   КНОПКА "КАРТА ДНЯ"
# ===============================
@card_router.message(F.text == "🃏 Карта дня")
async def open_tarot_webapp(message: types.Message):
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(
                    text="✨ Витягнути карту (міні-гра)",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ],
    )
    await message.answer(
        "🔮 Обери карту дня через інтерактивну колоду:", reply_markup=markup
    )


# ===============================
#       ОБРОБКА WEBAPP
# ===============================
@card_router.message(
    F.web_app_data.func(
        lambda d: d and d.data and json.loads(d.data).get("action") == "pick_card"
    )
)
async def on_webapp_data(message: types.Message):

    try:
        data = json.loads(message.web_app_data.data)
        print("[DEBUG] WebApp:", data)

        if data.get("action") != "pick_card":
            return

        chosen = data["chosen"]
        card_name = chosen["name"]
        upright = chosen["upright"]

        # --- 1️⃣ Тягнемо картку з TAROT_CARDS ---
        card_info = TAROT_CARDS.get(card_name)
        if not card_info:
            await message.answer("⚠️ Невідома карта.")
            return

        card_ua = card_info["ua_name"]
        img_path = card_info["image"]
        orientation = "⬆️" if upright else "⬇️"
        display_name = f"{card_ua} {orientation}"

        # --- 2️⃣ Фото картки ---
        card_img = load_card_image(img_path, upright)

        await message.answer_photo(
            photo=types.BufferedInputFile(card_img.getvalue(), filename="card.jpg"),
            caption=f"<b>{display_name}</b>",
            parse_mode="HTML",
        )

        # --- 3️⃣ Бананова анімація ---
        load_msg = await message.answer("🍌 Завантаження тлумачення…")

        async def banana_anim():
            n = 0
            while True:
                n = (n + 1) % 11
                bar = "🍌" * n + "▫️" * (10 - n)
                try:
                    await load_msg.edit_text(f"🍌 Завантаження тлумачення…\n{bar}")
                except:
                    return
                await asyncio.sleep(0.25)

        anim_task = asyncio.create_task(banana_anim())

        # --- 4️⃣ GPT ТЛУМАЧЕННЯ (Без n8n!) ---
        interpretation = await interpret_card(display_name)

        # --- 5️⃣ Stop animation ---
        anim_task.cancel()
        try:
            await load_msg.delete()
        except:
            pass

        # --- 6️⃣ Відповідь ---
        await message.answer(
            f"<b>{display_name}</b>\n\n{interpretation}",
            parse_mode="HTML",
            reply_markup=menu,
        )

    except Exception as e:
        print("ERROR:", e)
        await message.answer("⚠️ Помилка при обробці картки.")

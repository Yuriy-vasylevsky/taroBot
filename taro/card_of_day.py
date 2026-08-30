
from modules.user_stats_db import init_db
from datetime import datetime
import json
import asyncio
import aiosqlite
import os
from aiogram import Router, types, F
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    BufferedInputFile,
)
from PIL import Image
import io
from openai import AsyncOpenAI
from typing import Optional
import config
from cards_data import TAROT_CARDS
from modules.menu import popular_menu

card_router = Router()
client = AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)

WEBAPP_URL = "https://yuriy-vasylevsky.github.io/tarot-webapp/"

# Універсальний DB_PATH
DB_PATH = (
    "/data/tarot_users.db" if os.getenv("RAILWAY_ENVIRONMENT") else "tarot_users.db"
)

CARD_LIMIT_IMAGE = "assets/77.png"
CARD_TIME_OVER_IMAGE = "assets/77.png"

print(f"✅ Карта дня модуль завантажено | DB_PATH = {DB_PATH}")


# ====================== БАЗА ДАНИХ ======================

async def can_pick_card(user_id: int) -> bool:
    """Чи можна витягнути карту сьогодні (один раз до 14:00)"""
    
    await init_db()                     # створює таблицю, якщо її немає

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT last_card_picked_at FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()

    if not row or not row[0]:
        return True

    try:
        last = datetime.fromisoformat(row[0])
    except:
        return True

    now = datetime.now()

    if last.date() == now.date():
        return False   # вже витягнув сьогодні

    return now.hour < 12


async def update_last_card_picked_time(user_id: int):
    """Оновлює час витягування (викликати тільки після успішного витягування)"""
    await init_db()  # гарантія, що таблиця існує

    now = datetime.now().isoformat(timespec="seconds")  # стандартний ISO з 'T'

    async with aiosqlite.connect(DB_PATH) as db:
        # Створюємо рядок, якщо користувача ще немає
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        # Оновлюємо час
        await db.execute(
            "UPDATE users SET last_card_picked_at = ? WHERE user_id = ?", 
            (now, user_id)
        )
        await db.commit()
    
    print(f"✅ Час витягування карти оновлено для user {user_id}")


# ====================== ЗОБРАЖЕННЯ ======================
def load_card_image(path: str, upright: bool):
    img = Image.open(path)
    if not upright:
        img = img.rotate(180, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def load_notification_image(path: str) -> Optional[BufferedInputFile]:
    try:
        with open(path, "rb") as f:
            return BufferedInputFile(f.read(), filename="notification.png")
    except Exception as e:
        print(f"[ERROR] Не вдалося завантажити зображення {path}: {e}")
        return None


# ====================== GPT ======================
SYSTEM_PROMPT = """
Ти — досвідчений містичний таролог-наставник.
Дай відповідь українською, тепло, структуровано.

Структура відповіді:
1) 🔮 Ключова тема дня
2) ✨ Енергія дня
3) 💡 Порада
4) ⚠️ Чого уникати
"""


async def interpret_card(display_name: str):
    completion = await client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Карта дня: {display_name}\nДай тлумачення згідно структури.",
            },
        ],
        temperature=0.85,
    )
    return completion.choices[0].message.content


# ====================== ХЕНДЛЕРИ ======================
@card_router.message(F.text == "🃏 Карта дня")
async def open_tarot_webapp(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()

    print(f"🃏 Запит карти дня від user {user_id} | година: {now.hour}")

    if now.hour >= 12:
        img = load_notification_image(CARD_TIME_OVER_IMAGE)
        text = "⚠️ Карта дня більше не доступна сьогодні.\n🌅 Спробуй знову завтра."
        await (message.answer_photo(photo=img, caption=text) if img else message.answer(text))
        return

    if not await can_pick_card(user_id):
        img = load_notification_image(CARD_LIMIT_IMAGE)
        text = "⚠️ Ти вже витягнув карту дня сьогодні.\n✨ Нова карта буде доступна завтра до 14:00."
        await (message.answer_photo(photo=img, caption=text) if img else message.answer(text))
        return

    # Показуємо WebApp
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text="✨ Витягнути карту (міні-гра)", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    await message.answer("🔮 Обери карту дня через інтерактивну колоду:", reply_markup=markup)


@card_router.message(F.web_app_data)
async def on_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("action") != "pick_card":
            return

        chosen = data["chosen"]
        card_name = chosen["name"]
        upright = chosen["upright"]

        card_info = TAROT_CARDS.get(card_name)
        if not card_info:
            await message.answer("⚠️ Невідома карта.")
            return

        display_name = f"{card_info['ua_name']} {'⬆️' if upright else '⬇️'}"

        # Фото карти
        card_img = load_card_image(card_info["image"], upright)
        await message.answer_photo(
            photo=BufferedInputFile(card_img.getvalue(), filename="card.jpg"),
            caption=f"<b>{display_name}</b>",
            parse_mode="HTML",
        )

        # Анімація + тлумачення
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

        interpretation = await interpret_card(display_name)

        anim_task.cancel()
        try:
            await load_msg.delete()
        except:
            pass

        # Зберігаємо, що карта витягнута
        await update_last_card_picked_time(message.from_user.id)

        await message.answer(
            f"<b>{display_name}</b>\n\n{interpretation}",
            parse_mode="HTML",
            reply_markup=popular_menu,
        )

    except Exception as e:
        print(f"❌ Помилка обробки webapp даних: {e}")
        await message.answer("⚠️ Сталася помилка при обробці карти.")

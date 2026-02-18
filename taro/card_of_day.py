# from modules.menu import popular_menu
# import json
# import asyncio
# import aiosqlite
# from aiogram import Router, types, F
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, FSInputFile, BufferedInputFile
# from PIL import Image
# import io
# from openai import AsyncOpenAI
# from datetime import datetime
# from typing import Optional
# from cards_data import TAROT_CARDS
# import config

# # Ініціалізація
# card_router = Router()
# client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# WEBAPP_URL = "https://yuriy-vasylevsky.github.io/tarot-webapp/"
# # DB_PATH = "tarot_users.db"
# DB_PATH = "/data/tarot_users.db"


# # Шляхи до зображень для сповіщень
# CARD_LIMIT_IMAGE = "assets/77.png"  # Коли карта вже витягнута
# CARD_TIME_OVER_IMAGE = "assets/77.png"  # Коли час минув (після 14:00)


# # ======================
# #  ФУНКЦІЇ БАЗИ ДАНИХ
# # ======================


# async def can_pick_card(user_id: int) -> bool:
#     """Перевіряє, чи можна витягнути карту до 14 години дня, і чи ще не витягнута картка цього дня."""
#     async with aiosqlite.connect(DB_PATH) as db:
#         cur = await db.execute(
#             "SELECT last_card_picked_at FROM users WHERE user_id = ?", (user_id,)
#         )
#         row = await cur.fetchone()

#     current_time = datetime.now()

#     if row and row[0]:
#         last_card_time = datetime.fromisoformat(row[0])

#         # Перевірка, чи картка була витягнута цього дня після 14 годин
#         if last_card_time.date() == current_time.date():
#             if last_card_time.hour >= 14:
#                 return False  # Картку можна витягнути лише до 14 годин того ж дня
#             return False  # Якщо картка вже була витягнута цього дня, не дозволяємо повторно витягнути її

#     return True  # Картку можна витягнути, якщо ще не витягувалась сьогодні


# async def update_last_card_picked_time(user_id: int):
#     """Оновлює час останнього витягування карти для користувача."""
#     now = datetime.now().isoformat(sep=" ", timespec="seconds")
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute(
#             "UPDATE users SET last_card_picked_at = ? WHERE user_id = ?", (now, user_id)
#         )
#         await db.commit()


# # ======================
# #  ЗАВАНТАЖЕННЯ КАРТИ
# # ======================
# def load_card_image(path: str, upright: bool):
#     """Створює BytesIO з перевернутою/прямою карткою."""
#     img = Image.open(path)
#     if not upright:
#         img = img.rotate(180, expand=True)

#     buf = io.BytesIO()
#     img.save(buf, format="JPEG")
#     buf.seek(0)
#     return buf


# def load_notification_image(path: str) -> Optional[BufferedInputFile]:
#     """
#     Завантажує PNG-зображення для сповіщення.

#     Args:
#         path: Шлях до PNG файлу

#     Returns:
#         BufferedInputFile або None якщо файл не знайдено
#     """
#     try:
#         with open(path, "rb") as f:
#             img_bytes = f.read()
#         return BufferedInputFile(img_bytes, filename="notification.png")
#     except FileNotFoundError:
#         return None
#     except Exception as e:
#         print(f"[ERROR] Failed to load notification image {path}: {e}")
#         return None


# # ======================
# #  SYSTEM PROMPT GPT
# # ======================
# SYSTEM_PROMPT = """
# Ти — досвідчений містичний таролог-наставник.
# Дай відповідь українською
# Будь теплим, інтуїтивним, але чітким і структурованим.

# Структура відповіді:
# 1) 🔮 Ключова тема дня
# 2) ✨ Енергія дня
# 3) 💡 Порада
# 4) ⚠️ Чого уникати

# Пиши образно, красиво, але без зайвої "езотеричної води".
# """


# async def interpret_card(display_name: str):
#     """Отримує тлумачення карти напряму від GPT."""
#     prompt = f"Карта дня: {display_name}\nДай тлумачення згідно структури."

#     completion = await client.chat.completions.create(
#         model="gpt-4.1-mini",
#         messages=[
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": prompt},
#         ],
#         max_tokens=450,
#         temperature=0.9,
#     )

#     return completion.choices[0].message.content


# # ======================
# #  КНОПКА "КАРТА ДНЯ"
# # ======================

# @card_router.message(F.text == "🃏 Карта дня")
# async def open_tarot_webapp(message: types.Message):
#     """Обробка кнопки для витягування карти дня."""
#     user_id = message.from_user.id
#     current_time = datetime.now()

#     # Перевірка часу (після 14:00)
#     if current_time.hour >= 14:
#         notification_img = load_notification_image(CARD_TIME_OVER_IMAGE)

#         if notification_img:
#             await message.answer_photo(
#                 photo=notification_img,
#                 caption="⚠️ Карта дня більше не доступна сьогодні.\n"
#                         "🌅 Спробуй знову завтра до 14:00.",
#                 parse_mode="HTML"
#             )
#         else:
#             await message.answer(
#                 "⚠️ Карта дня більше не доступна сьогодні.\n"
#                 "🌅 Спробуй знову завтра до 14:00."
#             )
#         return

#     # Перевірка, чи можна витягнути карту
#     if not await can_pick_card(user_id):
#         notification_img = load_notification_image(CARD_LIMIT_IMAGE)

#         if notification_img:
#             await message.answer_photo(
#                 photo=notification_img,
#                 caption="⚠️ Карта дня доступна лише один раз на день до 14:00.\n"
#                         "✨ Твоя карта вже чекає на тебе завтра!",
#                 parse_mode="HTML"
#             )
#         else:
#             await message.answer(
#                 "⚠️ Карта дня доступна лише один раз на день до 14:00.\n"
#                 "✨ Твоя карта вже чекає на тебе завтра!"
#             )
#         return

#     # Якщо все ок - показуємо WebApp
#     markup = ReplyKeyboardMarkup(
#         resize_keyboard=True,
#         keyboard=[
#             [
#                 KeyboardButton(
#                     text="✨ Витягнути карту (міні-гра)",
#                     web_app=WebAppInfo(url=WEBAPP_URL),
#                 )
#             ]
#         ],
#     )
#     await message.answer(
#         "🔮 Обери карту дня через інтерактивну колоду:",
#         reply_markup=markup
#     )

#     # Оновлюємо час останнього витягування карти
#     await update_last_card_picked_time(user_id)


# # ======================
# #  ОБРОБКА WEBAPP
# # ======================
# @card_router.message(
#     F.web_app_data.func(
#         lambda d: d and d.data and json.loads(d.data).get("action") == "pick_card"
#     )
# )
# async def on_webapp_data(message: types.Message):
#     """Обробка даних після вибору карти в веб-додатку."""
#     try:
#         data = json.loads(message.web_app_data.data)
#         print("[DEBUG] WebApp:", data)

#         if data.get("action") != "pick_card":
#             return

#         chosen = data["chosen"]
#         card_name = chosen["name"]
#         upright = chosen["upright"]

#         # --- Тягнемо картку з TAROT_CARDS ---
#         card_info = TAROT_CARDS.get(card_name)
#         if not card_info:
#             await message.answer("⚠️ Невідома карта.")
#             return

#         card_ua = card_info["ua_name"]
#         img_path = card_info["image"]
#         orientation = "⬆️" if upright else "⬇️"
#         display_name = f"{card_ua} {orientation}"

#         # --- Фото картки ---
#         card_img = load_card_image(img_path, upright)

#         await message.answer_photo(
#             photo=types.BufferedInputFile(card_img.getvalue(), filename="card.jpg"),
#             caption=f"<b>{display_name}</b>",
#             parse_mode="HTML",
#         )

#         # --- Бананова анімація ---
#         load_msg = await message.answer("🍌 Завантаження тлумачення…")

#         async def banana_anim():
#             n = 0
#             while True:
#                 n = (n + 1) % 11
#                 bar = "🍌" * n + "▫️" * (10 - n)
#                 try:
#                     await load_msg.edit_text(f"🍌 Завантаження тлумачення…\n{bar}")
#                 except:
#                     return
#                 await asyncio.sleep(0.25)

#         anim_task = asyncio.create_task(banana_anim())

#         # --- GPT ТЛУМАЧЕННЯ ---
#         interpretation = await interpret_card(display_name)

#         # --- Stop animation ---
#         anim_task.cancel()
#         try:
#             await load_msg.delete()
#         except:
#             pass

#         # --- Відповідь ---
#         await message.answer(
#             f"<b>{display_name}</b>\n\n{interpretation}",
#             parse_mode="HTML",
#             reply_markup=popular_menu,
#         )

#     except Exception as e:
#         print("ERROR:", e)
#         await message.answer("⚠️ Помилка при обробці картки.")

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
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

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
        return last.hour < 14  # дозволено тільки до 14:00

    return True


async def update_last_card_picked_time(user_id: int):
    """Оновлює час витягування (викликати тільки після успішного витягування)"""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_card_picked_at = ? WHERE user_id = ?", (now, user_id)
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
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Карта дня: {display_name}\nДай тлумачення згідно структури.",
            },
        ],
        max_tokens=450,
        temperature=0.85,
    )
    return completion.choices[0].message.content


# ====================== ХЕНДЛЕРИ ======================
@card_router.message(F.text == "🃏 Карта дня")
async def open_tarot_webapp(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()

    print(f"🃏 Запит карти дня від user {user_id}")

    if now.hour >= 14:
        img = load_notification_image(CARD_TIME_OVER_IMAGE)
        text = "⚠️ Карта дня більше не доступна сьогодні.\n🌅 Спробуй знову завтра до 14:00."
        (
            await message.answer_photo(photo=img, caption=text)
            if img
            else await message.answer(text)
        )
        return

    if not await can_pick_card(user_id):
        img = load_notification_image(CARD_LIMIT_IMAGE)
        text = "⚠️ Ти вже витягнув карту дня сьогодні.\n✨ Нова карта буде доступна завтра до 14:00."
        (
            await message.answer_photo(photo=img, caption=text)
            if img
            else await message.answer(text)
        )
        return

    # Показуємо WebApp
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

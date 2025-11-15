# import os
# import json
# import tempfile
# from PIL import Image
# from aiogram import Router, types, F
# from aiogram.types import FSInputFile, ReplyKeyboardRemove
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# import asyncio
# from modules.menu import menu
# from modules.animation import run_animation
# from modules.n8n_api import get_interpretation_from_n8n
# from cards_data import TAROT_CARDS  # твоя база карт з image + ua_name


# ask_taro = Router()


# # ======================
# #     СТАНИ
# # ======================
# class TarotDialog(StatesGroup):
#     waiting_for_question = State()
#     waiting_for_cards = State()


# # ======================
# #   КНОПКА "Діалог"
# # ======================
# @ask_taro.message(lambda msg: msg.text == "💬 Діалог з Таро")
# async def tarot_dialog_start(message: types.Message, state: FSMContext):
#     await message.answer(
#         "🔮 Задай своє питання Таро...", reply_markup=ReplyKeyboardRemove()
#     )
#     await state.set_state(TarotDialog.waiting_for_question)


# # ======================
# #  Після питання → кнопка WebApp
# # ======================
# @ask_taro.message(TarotDialog.waiting_for_question)
# async def tarot_dialog_question(message: types.Message, state: FSMContext):
#     question = message.text

#     # зберігаємо питання в FSM
#     await state.update_data(question=question)

#     # показуємо кнопку
#     keyboard = types.ReplyKeyboardMarkup(
#         resize_keyboard=True,
#         keyboard=[
#             [
#                 types.KeyboardButton(
#                     text="✨ Обрати 3 карти",
#                     web_app=types.WebAppInfo(
#                         url="https://yuriy-vasylevsky.github.io/tarodayweb"  # ← ВСТАВ СЮДИ URL 7-картового вебаппа
#                     ),
#                 )
#             ]
#         ],
#     )

#     await message.answer(
#         "🃏 Тепер обери 3 карти через інтерактивну колоду:", reply_markup=keyboard
#     )

#     await state.set_state(TarotDialog.waiting_for_cards)


# # ======================
# #    ЛОВИМО WebApp  → 3 карти
# # ======================
# @ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
# async def tarot_dialog_cards(message: types.Message, state: FSMContext):

#     data = json.loads(message.web_app_data.data)
#     print("[DEBUG] DIALOG WEBAPP:", data)

#     if data.get("action") != "three_cards":
#         return  # це не наше

#     chosen_cards = data["chosen"]  # список з 3 карт
#     state_data = await state.get_data()
#     question = state_data.get("question")

#     if not question:
#         await message.answer("⚠️ Сталася помилка — питання не знайдено.")
#         return

#     # ======================
#     #   ВІДПРАВЛЯЄМО 3 КАРТИ
#     # ======================
#     media = []
#     cards_display = []

#     for i, card in enumerate(chosen_cards, start=1):
#         eng = card["name"]  # "The Fool"
#         upright = card["upright"]  # True/False

#         card_info = TAROT_CARDS.get(eng)
#         if not card_info:
#             continue

#         img_path = card_info["image"]
#         ua_name = card_info["ua_name"]
#         orientation_ua = "⬆️" if upright else "⬇️"

#         # повертаємо картинку якщо перевернута
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
#             tmp_path = tmp.name

#         img = Image.open(img_path).convert("RGB")
#         if not upright:
#             img = img.rotate(180, expand=True)
#         img.save(tmp_path, "JPEG", quality=95)

#         media.append(
#             types.InputMediaPhoto(
#                 media=FSInputFile(tmp_path),
#                 caption="" if i > 1 else "🔮 Ваші карти",
#             )
#         )

#         cards_display.append(f"{i}. <b>{ua_name}</b> {orientation_ua}")

#     # # надсилаємо 3 карти одним повідомленням
#     # await message.answer_media_group(media)

#     # anim_task = asyncio.create_task(
#     #     run_animation(message, text="🔮 Тлумачення карт...", emoji="🔮")
#     # )

#     # try:
#     #     # ======================
#     #     #     ВИКЛИК N8N
#     #     # ======================
#     #     cards_for_ai = [
#     #         f"{TAROT_CARDS[c['name']]['ua_name']} ({'upright' if c['upright'] else 'reversed'})"
#     #         for c in chosen_cards
#     #     ]

#     #     interpretation = await get_interpretation_from_n8n(
#     #         cards_for_ai,
#     #         "three_card_dialog",
#     #         message.from_user.full_name,
#     #         question,
#     #     )

#     # finally:
#     #     # ======================
#     #     #     СТОП АНІМАЦІЯ
#     #     # ======================
#     #     anim_task.cancel()

#     # # ======================
#     # #     ВІДПОВІДЬ КОРИСТУВАЧУ
#     # # ======================
#     # await message.answer(
#     #     f"<b>❓ Питання:</b> {question}\n\n"
#     #     f"{chr(10).join(cards_display)}\n\n"
#     #     f"{interpretation}",
#     #     parse_mode="HTML",
#     #     reply_markup=menu,
#     # )

#     # ----------------- НАДСИЛАЄМО КАРТИ -----------------
#     await message.answer_media_group(media)

#     # ======================
#     #     БАНАНОВА АНІМАЦІЯ
#     # ======================
#     load_msg = await message.answer("🍌 Завантаження тлумачення…")

#     async def banana_anim():
#         n = 0
#         while True:
#             n = (n + 1) % 11
#             bar = "🍌" * n + "▫️" * (10 - n)
#             try:
#                 await load_msg.edit_text(f"🍌 Тлумачення карт…\n{bar}")
#             except:
#                 return
#             await asyncio.sleep(0.25)

#     anim_task = asyncio.create_task(banana_anim())

#     # ======================
#     #   ВИКЛИК N8N (3 карти)
#     # ======================
#     cards_for_ai = [
#         f"{TAROT_CARDS[c['name']]['ua_name']} ({'upright' if c['upright'] else 'reversed'})"
#         for c in chosen_cards
#     ]

#     interpretation = await get_interpretation_from_n8n(
#         cards_for_ai,
#         "three_card_dialog",
#         message.from_user.full_name,
#         question
#     )

#     # ======================
#     #   ЗУПИНЯЄМО АНІМАЦІЮ
#     # ======================
#     anim_task.cancel()
#     try:
#         await load_msg.delete()
#     except:
#         pass

#     # ======================
#     #      ВІДПОВІДЬ
#     # ======================
#     await message.answer(
#         f"<b>❓ Питання:</b> {question}\n\n"
#         f"{chr(10).join(cards_display)}\n\n"
#         f"{interpretation}",
#         parse_mode="HTML",
#         reply_markup=menu,
#     )

#     # чистимо state
#     await state.clear()

#     # чистимо тимчасові файли
#     for m in media:
#         try:
#             os.remove(m.media.path)
#         except:
#             pass

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
from modules.animation import run_animation
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
Дай відповідь українською мовою.

Структура відповіді:
1) 🔮 Підсумок (так / скоріше так / нейтрально / скоріше ні / ні)
2) ✨ Короткий розбір кожної карти
3) 🌙 Висновок
4) 💛 Мантра
"""


# ======================
#     СТАНИ
# ======================
class TarotDialog(StatesGroup):
    waiting_for_question = State()
    waiting_for_cards = State()


# ======================
#   КНОПКА "Діалог"
# ======================
@ask_taro.message(lambda msg: msg.text == "💬 Діалог з Таро")
async def tarot_dialog_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🔮 Задай своє питання Таро...", reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(TarotDialog.waiting_for_question)


# ======================
#  Після питання → кнопка WebApp
# ======================
@ask_taro.message(TarotDialog.waiting_for_question)
async def tarot_dialog_question(message: types.Message, state: FSMContext):
    question = message.text
    await state.update_data(question=question)

    keyboard = types.ReplyKeyboardMarkup(
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

    await message.answer(
        "🃏 Тепер обери 3 карти через інтерактивну колоду:", reply_markup=keyboard
    )

    await state.set_state(TarotDialog.waiting_for_cards)


# ======================
#   GPT ТЛУМАЧЕННЯ
# ======================
async def interpret_cards_gpt(question: str, cards_display: str):
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Питання користувача:\n{question}\n\n"
        f"Витягнуті карти:\n{cards_display}\n\n"
        f"Дай гарне, містичне і структуроване тлумачення:"
    )

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.9
    )

    return response.choices[0].message.content


# ======================
#    ЛОВИМО 3 КАРТИ з WebApp
# ======================
@ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
async def tarot_dialog_cards(message: types.Message, state: FSMContext):

    data = json.loads(message.web_app_data.data)
    print("[DEBUG] DIALOG WEBAPP:", data)

    if data.get("action") != "three_cards":
        return

    chosen_cards = data["chosen"]
    question = (await state.get_data()).get("question")

    # ======================
    #   ФОТО + СПИСОК
    # ======================
    media = []
    cards_display = []

    for i, card in enumerate(chosen_cards, start=1):
        eng = card["name"]
        upright = card["upright"]

        card_info = TAROT_CARDS.get(eng)
        if not card_info:
            continue

        img_path = card_info["image"]
        ua_name = card_info["ua_name"]
        arrow = "⬆️" if upright else "⬇️"

        # повертаємо зображення якщо перевернуте
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp_path = tmp.name

        img = Image.open(img_path).convert("RGB")
        if not upright:
            img = img.rotate(180, expand=True)
        img.save(tmp_path, "JPEG", quality=95)

        media.append(
            types.InputMediaPhoto(
                media=FSInputFile(tmp_path),
                caption="" if i > 1 else "🔮 Ваші карти",
            )
        )

        cards_display.append(f"{i}. {ua_name} {arrow}")

    await message.answer_media_group(media)

    # ======================
    #   АНІМАЦІЯ
    # ======================
    load_msg = await message.answer("🔮 Тлумачення…")

    async def anim():
        n = 0
        while True:
            bar = "🔮" * (n % 5 + 1)
            try:
                await load_msg.edit_text(f"🔮 Тлумачення…\n{bar}")
            except:
                break
            await asyncio.sleep(0.25)
            n += 1

    anim_task = asyncio.create_task(anim())

    # ======================
    # GPT ТЛУМАЧЕННЯ
    # ======================
    interpretation = await interpret_cards_gpt(
        question,
        "\n".join(cards_display)
    )

    anim_task.cancel()
    try: await load_msg.delete()
    except: pass

    # ======================
    # ВІДПОВІДЬ
    # ======================
    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    # чистимо FSM і tmp
    await state.clear()

    for m in media:
        try:
            os.remove(m.media.path)
        except:
            pass

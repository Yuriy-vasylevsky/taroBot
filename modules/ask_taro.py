

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
# from cards_data import TAROT_CARDS

# from openai import AsyncOpenAI
# import config

# ask_taro = Router()

# client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# # ======================
# #     SYSTEM PROMPT
# # ======================
# SYSTEM_PROMPT = """
# Ти — досвідчений таролог-наставник.
# Говори глибоко, тепло, інтуїтивно.
# Уникай мотлоху, пиши сильні, красиві смисли.
# Дай відповідь українською абр російською мовою в залежності на якій до тебе звертаються.
# будь також психологом, щоб людина думала що ти її розумієш.
# Структура відповіді:
# 1) 🔮 Підсумок (так / скоріше так / нейтрально / скоріше ні / ні)
# 2) ✨ Короткий розбір кожної карти
# 3) 🌙 Висновок
# 4) 💛 Мантра
# """


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
# # @ask_taro.message(TarotDialog.waiting_for_question)
# # async def tarot_dialog_question(message: types.Message, state: FSMContext):
# #     question = message.text
# #     await state.update_data(question=question)

# #     keyboard = types.ReplyKeyboardMarkup(
# #         resize_keyboard=True,
# #         keyboard=[
# #             [
# #                 types.KeyboardButton(
# #                     text="✨ Обрати 3 карти",
# #                     web_app=types.WebAppInfo(
# #                         url="https://yuriy-vasylevsky.github.io/tarodayweb"
# #                     ),
# #                 )
# #             ]
# #         ],
# #     )

# #     await message.answer(
# #         "🃏 Тепер обери 3 карти через інтерактивну колоду:", reply_markup=keyboard
# #     )

# #     await state.set_state(TarotDialog.waiting_for_cards)
# @ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
# async def tarot_dialog_cards(message: types.Message, state: FSMContext):

#     data = json.loads(message.web_app_data.data)
#     print("[DEBUG] DIALOG WEBAPP:", data)

#     if data.get("action") != "three_cards":
#         return

#     chosen_cards = data["chosen"]
#     question = (await state.get_data()).get("question")

#     # ======================
#     #   ЗБИРАЄМО ІНФУ ДЛЯ 3 КАРТ
#     # ======================
#     img_paths = []
#     uprights = []
#     cards_display = []

#     for i, card in enumerate(chosen_cards, start=1):
#         eng = card["name"]
#         upright = card["upright"]

#         card_info = TAROT_CARDS.get(eng)
#         if not card_info:
#             continue

#         img_paths.append(card_info["image"])
#         uprights.append(upright)

#         ua_name = card_info["ua_name"]
#         arrow = "⬆️" if upright else "⬇️"
#         cards_display.append(f"{i}. {ua_name} {arrow}")

#     # ======================
#     #   ОБ’ЄДНАННЯ В ОДНЕ ФОТО
#     # ======================
#     final_img_path = combine_three_cards(img_paths, uprights)

#     await message.answer_photo(
#         FSInputFile(final_img_path),
#         caption="🔮 Ваш розклад із 3 карт"
#     )

#     # ======================
#     #   АНІМАЦІЯ
#     # ======================
#     load_msg = await message.answer("🔮 Тлумачення…")

#     async def anim():
#         n = 0
#         while True:
#             bar = "🔮" * (n % 5 + 1)
#             try:
#                 await load_msg.edit_text(f"🔮 Тлумачення…\n{bar}")
#             except:
#                 break
#             await asyncio.sleep(0.25)
#             n += 1

#     anim_task = asyncio.create_task(anim())

#     # ======================
#     # GPT ТЛУМАЧЕННЯ
#     # ======================
#     interpretation = await interpret_cards_gpt(
#         question,
#         "\n".join(cards_display)
#     )

#     anim_task.cancel()
#     try: await load_msg.delete()
#     except: pass

#     # ======================
#     # ВІДПОВІДЬ GPT
#     # ======================
#     await message.answer(
#         f"<b>❓ Питання:</b> {question}\n\n"
#         f"{chr(10).join(cards_display)}\n\n"
#         f"{interpretation}",
#         parse_mode="HTML",
#         reply_markup=menu,
#     )

#     # ======================
#     #   Очищення
#     # ======================
#     try:
#         os.remove(final_img_path)
#     except:
#         pass

#     await state.clear()


# # ======================
# #   GPT ТЛУМАЧЕННЯ
# # ======================
# async def interpret_cards_gpt(question: str, cards_display: str):
#     prompt = (
#         f"{SYSTEM_PROMPT}\n\n"
#         f"Питання користувача:\n{question}\n\n"
#         f"Витягнуті карти:\n{cards_display}\n\n"
#         f"Дай гарне, містичне і структуроване тлумачення:"
#     )

#     response = await client.chat.completions.create(
#         model="gpt-4.1-mini",
#         messages=[{"role": "system", "content": SYSTEM_PROMPT},
#                   {"role": "user", "content": prompt}],
#         max_tokens=600,
#         temperature=0.9
#     )

#     return response.choices[0].message.content


# # ======================
# #    ЛОВИМО 3 КАРТИ з WebApp
# # ======================
# @ask_taro.message(TarotDialog.waiting_for_cards, F.web_app_data)
# async def tarot_dialog_cards(message: types.Message, state: FSMContext):

#     data = json.loads(message.web_app_data.data)
#     print("[DEBUG] DIALOG WEBAPP:", data)

#     if data.get("action") != "three_cards":
#         return

#     chosen_cards = data["chosen"]
#     question = (await state.get_data()).get("question")

#     # ======================
#     #   ФОТО + СПИСОК
#     # ======================
#     media = []
#     cards_display = []

#     for i, card in enumerate(chosen_cards, start=1):
#         eng = card["name"]
#         upright = card["upright"]

#         card_info = TAROT_CARDS.get(eng)
#         if not card_info:
#             continue

#         img_path = card_info["image"]
#         ua_name = card_info["ua_name"]
#         arrow = "⬆️" if upright else "⬇️"

#         # повертаємо зображення якщо перевернуте
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

#         cards_display.append(f"{i}. {ua_name} {arrow}")

#     await message.answer_media_group(media)

#     # ======================
#     #   АНІМАЦІЯ
#     # ======================
#     load_msg = await message.answer("🔮 Тлумачення…")

#     async def anim():
#         n = 0
#         while True:
#             bar = "🔮" * (n % 5 + 1)
#             try:
#                 await load_msg.edit_text(f"🔮 Тлумачення…\n{bar}")
#             except:
#                 break
#             await asyncio.sleep(0.25)
#             n += 1

#     anim_task = asyncio.create_task(anim())

#     # ======================
#     # GPT ТЛУМАЧЕННЯ
#     # ======================
#     interpretation = await interpret_cards_gpt(
#         question,
#         "\n".join(cards_display)
#     )

#     anim_task.cancel()
#     try: await load_msg.delete()
#     except: pass

#     # ======================
#     # ВІДПОВІДЬ
#     # ======================
#     await message.answer(
#         f"<b>❓ Питання:</b> {question}\n\n"
#         f"{chr(10).join(cards_display)}\n\n"
#         f"{interpretation}",
#         parse_mode="HTML",
#         reply_markup=menu,
#     )

#     # чистимо FSM і tmp
#     await state.clear()

#     for m in media:
#         try:
#             os.remove(m.media.path)
#         except:
#             pass


# def combine_three_cards(paths, uprights, background_color=(30, 30, 30)):
#     """
#     Об’єднує 3 карти в одне зображення.
#     paths      – список шляхів до зображень карт (3 шт)
#     uprights   – список True/False (пряма/перевернута)
#     background_color – фон (ти підставиш свій)
#     """

#     imgs = []
#     for path, up in zip(paths, uprights):
#         img = Image.open(path).convert("RGB")
#         if not up:
#             img = img.rotate(180, expand=True)
#         imgs.append(img)

#     w, h = imgs[0].size
#     spacing = 50  # можна змінити

#     total_w = w * 3 + spacing * 2
#     combined = Image.new("RGB", (total_w, h), background_color)

#     combined.paste(imgs[0], (0, 0))
#     combined.paste(imgs[1], (w + spacing, 0))
#     combined.paste(imgs[2], ((w + spacing) * 2, 0))

#     buf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
#     combined.save(buf, "JPEG", quality=95)
#     buf.close()

#     return buf.name


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


# ======================
#   ОБ’ЄДНАТИ 3 КАРТИ + PNG ФОН
# ======================
# def combine_three_cards_with_background(paths, uprights, background_path="background.png"):
#     """
#     Об'єднує 3 карти на PNG-фоні.
#     paths     – list із 3 шляхів до карт
#     uprights  – list True/False
#     background_path – шлях до PNG фону
#     """

#     # ------- Завантажуємо фон -------
#     bg = Image.open(background_path).convert("RGBA")

#     # ------- Завантажуємо і готуємо карти -------
#     card_imgs = []
#     for path, up in zip(paths, uprights):
#         img = Image.open(path).convert("RGBA")
#         if not up:
#             img = img.rotate(180, expand=True)
#         card_imgs.append(img)

#     # Масштабуємо карти під фон (не обов’язково, але красиво)
#     W, H = bg.size
#     card_w = int(W * 0.28)
#     ratio = card_w / card_imgs[0].size[0]
#     card_h = int(card_imgs[0].size[1] * ratio)
#     card_imgs = [img.resize((card_w, card_h), Image.LANCZOS) for img in card_imgs]

#     # ------- Координати розташування -------
#     spacing = int(W * 0.05)

#     x1 = int(W * 0.05)
#     x2 = x1 + card_w + spacing
#     x3 = x2 + card_w + spacing
#     y = int((H - card_h) / 2)

#     # ------- Накладаємо карти на фон -------
#     bg.alpha_composite(card_imgs[0], (x1, y))
#     bg.alpha_composite(card_imgs[1], (x2, y))
#     bg.alpha_composite(card_imgs[2], (x3, y))

#     # ------- Зберігаємо -------
#     temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
#     bg.convert("RGB").save(temp.name, "PNG", quality=95)

#     return temp.name

def combine_three_cards_with_background(paths, uprights, background_path="background.png"):
    """
    Об'єднує 3 карти на PNG-фоні з ідеальним центруванням.
    """

    # ------- Завантажуємо фон -------
    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size  # ширина/висота фону

    # ------- Завантажуємо і готуємо карти -------
    cards = []
    for path, up in zip(paths, uprights):
        img = Image.open(path).convert("RGBA")
        if not up:
            img = img.rotate(180, expand=True)
        cards.append(img)

    # ------- Масштаб під фон -------
    card_w = int(W * 0.25)   # карта буде займати 25% ширини фону
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)

    cards = [c.resize((card_w, card_h), Image.LANCZOS) for c in cards]

    # ------- Центрування -------
    total_width = card_w * 3
    spacing = int(W * 0.03)  # 3% від ширини — розумний проміжок

    total_width += spacing * 2  # додаємо проміжки

    start_x = int((W - total_width) / 2)  # ЦЕНТРУЄМО ПО ГОРИЗОНТАЛІ
    y = int((H - card_h) / 2)             # ЦЕНТРУЄМО ПО ВЕРТИКАЛІ

    x_positions = [
        start_x,
        start_x + card_w + spacing,
        start_x + (card_w + spacing) * 2
    ]

    # ------- Накладаємо карти -------
    for img, x in zip(cards, x_positions):
        bg.alpha_composite(img, (x, y))

    # ------- Зберігаємо -------
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.convert("RGB").save(temp.name, "PNG", quality=95)

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

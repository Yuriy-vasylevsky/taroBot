# # dialog_gpt_tarot.py
# # Телеграм ТАРО-ЧАТ з GPT 4.1-mini
# # Живий діалоговий таролог: GPT сам визначає коли тягнути карти, сам просить карти, сам тлумачить

# import re
# import random
# import asyncio
# import io
# from typing import List, Dict
# from modules.menu import menu
# from aiogram import Router, types, F
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.context import FSMContext
# from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# from openai import AsyncOpenAI
# from cards_data import TAROT_CARDS
# from PIL import Image
# import config

# dialog_router = Router()

# # GPT client init
# client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# # ================= MESSAGE HISTORY PER USER ===================

# user_histories: Dict[int, List[Dict[str, str]]] = {}


# def get_history(user_id: int):
#     if user_id not in user_histories:
#         user_histories[user_id] = []
#     return user_histories[user_id]


# def add_message(user_id: int, role: str, content: str):
#     hist = get_history(user_id)
#     hist.append({"role": role, "content": content})
#     # обмежуємо історію
#     if len(hist) > 30:
#         user_histories[user_id] = hist[-30:]


# # =================== CARD DRAWING ===================


# def draw_cards(amount: int):
#     names = list(TAROT_CARDS.keys())
#     chosen = random.sample(names, amount)
#     result = []
#     for name in chosen:
#         upright = random.choice([True, False])
#         ua = TAROT_CARDS[name]["ua_name"]
#         img_path = TAROT_CARDS[name]["image"]
#         result.append({"code": name, "ua": ua, "upright": upright, "image": img_path})
#     return result


# def load_img(path: str, upright: bool):
#     img = Image.open(path)
#     if not upright:
#         img = img.rotate(180, expand=True)

#     buf = io.BytesIO()
#     img.save(buf, format="JPEG")
#     buf.seek(0)
#     return buf


# # ================== GPT SYSTEM PROMPT ==================

# SYSTEM_PROMPT = """
# Ти — живий, теплий, інтуїтивний, містичний таролог-наставник.
# Ти говориш як людина, але глибоко і проникливо.
# Ти не просто тлумачиш карти — ти ведеш діалог, ставиш уточнення, цікавишся деталями.

# Ти можеш сказати:
# - «Я відчуваю, що тут треба витягнути карту…»
# - «Давай поглянемо глибше — я би взяв три карти.»
# - «Готовий подивитися? Можу витягнути зараз.»
# - «Тут варто зробити повний розклад на 5 карт.»

# НЕ використовуй теги (#draw:3, JSON, XML).
# Проси карти людською мовою.
# Якщо користувач погоджується — просто продовжуй бесіду.
# """

# # ================================================================


# class TarotChatFSM(StatesGroup):
#     chatting = State()


# EXIT_TEXT = "⬅️ Завершити бесіду"


# def dialog_kb():
#     return ReplyKeyboardMarkup(
#         resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]]
#     )


# # ================== START DIALOG ===================


# @dialog_router.message(F.text == "🔮 Живий Таро-чат")
# async def start_dialog(message: types.Message, state: FSMContext):
#     await state.set_state(TarotChatFSM.chatting)
#     user_histories[message.from_user.id] = []  # reset
#     add_message(message.from_user.id, "system", SYSTEM_PROMPT)

#     welcome = (
#         "✨ Я тут. Давай поговоримо так, ніби ти поруч.\n"
#         "Про що хочеш дізнатися сьогодні?"
#     )

#     add_message(message.from_user.id, "assistant", welcome)
#     await message.answer(welcome, reply_markup=dialog_kb())


# # ================== EXIT ===================


# @dialog_router.message(F.text == EXIT_TEXT)
# async def exit_dialog(message: types.Message, state: FSMContext):
#     await state.clear()
#     await message.answer("🔚 Я поруч, коли захочеш продовжити.", reply_markup=menu)


# # ================== MAIN CHAT ===================


# @dialog_router.message(TarotChatFSM.chatting)
# async def chat(message: types.Message, state: FSMContext):

#     user_id = message.from_user.id
#     text = message.text

#     add_message(user_id, "user", text)

#     # GPT answer
#     response = await client.chat.completions.create(
#         model="gpt-4.1-mini", messages=get_history(user_id), max_tokens=4000
#     )

#     reply = response.choices[0].message.content
#     add_message(user_id, "assistant", reply)

#     # ========================
#     # DETECT CARD REQUESTS
#     # ========================
#     # need_1 = re.search(r"\b1\s*карт", reply, re.IGNORECASE)
#     # need_3 = re.search(r"\b(3|три)\s*карт", reply, re.IGNORECASE)
#     # need_5 = re.search(r"\b(5|п’ять|пять)\s*карт", reply, re.IGNORECASE)

#     # # send GPT reply first
#     # await message.answer(reply)

#     # # if GPT did not request cards → done
#     # if not (need_1 or need_3 or need_5):
#     #     return

#     # # how many?
#     # if need_5:
#     #     amount = 5
#     # elif need_3:
#     #     amount = 3
#     # else:
#     #     amount = 1

#     # # draw cards
#     # cards = draw_cards(amount)

#     # # photo group
#     # media = []
#     # for idx, c in enumerate(cards):
#     #     buf = load_img(c["image"], c["upright"])
#     #     file = types.BufferedInputFile(buf.getvalue(), filename=f"card_{idx+1}.jpg")
#     #     arrow = "⬆️" if c["upright"] else "⬇️"
#     #     caption = f"{c['ua']} {arrow}" if idx == 0 else None
#     #     media.append(types.InputMediaPhoto(media=file, caption=caption))

#     # await message.answer_media_group(media)

#     # # send card info back to GPT
#     # cards_text = "Витягнуті карти:\n" + "\n".join(
#     #     f"{c['ua']} ({c['code']}) — {'пряма' if c['upright'] else 'перевернута'}"
#     #     for c in cards
#     # )

#     # add_message(user_id, "user", cards_text)

#     # follow = await client.chat.completions.create(
#     #     model="gpt-4.1-mini",
#     #     messages=get_history(user_id),
#     #     max_tokens=5000
#     # )

#     # final_reply = follow.choices[0].message.content
#     # add_message(user_id, "assistant", final_reply)

#     # await message.answer(final_reply)
#     # ========================
#     # DETECT CARD REQUESTS
#     # ========================
#     need_1 = re.search(r"\b1\s*карт", reply, re.IGNORECASE)
#     need_3 = re.search(r"\b(3|три)\s*карт", reply, re.IGNORECASE)
#     need_5 = re.search(r"\b(5|п’ять|пять)\s*карт", reply, re.IGNORECASE)

#     # send GPT reply first
#     await message.answer(reply)

#     # if GPT did not request cards → done
#     if not (need_1 or need_3 or need_5):
#         return

#     # how many?
#     if need_5:
#         amount = 5
#     elif need_3:
#         amount = 3
#     else:
#         amount = 1

#     # draw cards
#     cards = draw_cards(amount)

#     # ========================
#     # SEND CARDS TO USER
#     # ========================
#     if len(cards) == 1:
#         # ---- ONE CARD ----
#         c = cards[0]
#         buf = load_img(c["image"], c["upright"])
#         file = types.BufferedInputFile(buf.getvalue(), filename="card.jpg")
#         arrow = "⬆️" if c["upright"] else "⬇️"
#         caption = f"{c['ua']} {arrow}"

#         await message.answer_photo(photo=file, caption=caption)

#     else:
#         # ---- MULTI-CARD ALBUM (2+) ----
#         media = []
#         for idx, c in enumerate(cards):
#             buf = load_img(c["image"], c["upright"])
#             file = types.BufferedInputFile(buf.getvalue(), filename=f"card_{idx+1}.jpg")
#             arrow = "⬆️" if c["upright"] else "⬇️"
#             caption = f"{c['ua']} {arrow}" if idx == 0 else None
#             media.append(types.InputMediaPhoto(media=file, caption=caption))

#         await message.answer_media_group(media)

#     # ========================
#     # SEND CARDS BACK TO GPT FOR INTERPRETATION
#     # ========================
#     cards_text = "Витягнуті карти:\n" + "\n".join(
#         f"{c['ua']} ({c['code']}) — {'пряма' if c['upright'] else 'перевернута'}"
#         for c in cards
#     )

#     add_message(user_id, "user", cards_text)

#     follow = await client.chat.completions.create(
#         model="gpt-4.1-mini", messages=get_history(user_id), max_tokens=5000
#     )

#     final_reply = follow.choices[0].message.content
#     add_message(user_id, "assistant", final_reply)

#     await message.answer(final_reply)

# dialog_gpt_tarot.py
# Телеграм ТАРО-ЧАТ з GPT 4.1-mini
# Живий діалоговий таролог: GPT сам просить карти, а бот їх тягне і повертає GPT

import re
import random
import asyncio
import io
from typing import List, Dict
from modules.menu import menu
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from openai import AsyncOpenAI
from cards_data import TAROT_CARDS
from PIL import Image
import config

dialog_router = Router()

# GPT client init
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ================= MESSAGE HISTORY PER USER ===================

user_histories: Dict[int, List[Dict[str, str]]] = {}


def get_history(user_id: int):
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]


def add_message(user_id: int, role: str, content: str):
    hist = get_history(user_id)
    hist.append({"role": role, "content": content})
    if len(hist) > 30:
        user_histories[user_id] = hist[-30:]


# =================== CARD DRAWING ===================


def draw_cards(amount: int):
    names = list(TAROT_CARDS.keys())
    chosen = random.sample(names, amount)
    result = []
    for name in chosen:
        upright = random.choice([True, False])
        ua = TAROT_CARDS[name]["ua_name"]
        img_path = TAROT_CARDS[name]["image"]
        result.append({"code": name, "ua": ua, "upright": upright, "image": img_path})
    return result


def load_img(path: str, upright: bool):
    img = Image.open(path)
    if not upright:
        img = img.rotate(180, expand=True)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


# ================== GPT SYSTEM PROMPT ==================

SYSTEM_PROMPT = """
Ти — інтуїтивний таролог, але є важливе правило:

❗Ти НІКОЛИ не маєш права називати карту, описувати її, казати «я бачу карту», «я витягнув карту», «переді мною карта» або придумувати карти САМ.

Ти можеш тільки:
- запропонувати витягнути карту
- попросити зробити розклад
- написати «я готовий глянути карту»
- написати «я би взяв одну карту для ясності»

АЛЕ:
❗Ти НЕ можеш назвати карту або описати її, доки бот НЕ пришле текст:
"Витягнуті карти:".

Коли бот прислав "Витягнуті карти:", ти тлумачиш ТІЛЬКИ ці карти.
Все інше — заборонено.

Ти не дякуєш за карту, не просиш підтверджень, не говориш «дай знати коли тягнути».
Ти спілкуєшся тепло, м'яко, інтуїтивно.
"""


# ================================================================


class TarotChatFSM(StatesGroup):
    chatting = State()


EXIT_TEXT = "⬅️ Завершити бесіду"


def dialog_kb():
    return ReplyKeyboardMarkup(
        resize_keyboard=True, keyboard=[[KeyboardButton(text=EXIT_TEXT)]]
    )


# ================== START DIALOG ===================


@dialog_router.message(F.text == "🔮 Живий Таро-чат")
async def start_dialog(message: types.Message, state: FSMContext):
    await state.set_state(TarotChatFSM.chatting)
    user_histories[message.from_user.id] = []  # reset

    add_message(message.from_user.id, "system", SYSTEM_PROMPT)

    welcome = (
        "✨ Я тут. Давай поговоримо так, ніби ти поруч.\n"
        "Про що хочеш дізнатися сьогодні?"
    )

    add_message(message.from_user.id, "assistant", welcome)
    await message.answer(welcome, reply_markup=dialog_kb())


# ================== EXIT ===================


@dialog_router.message(F.text == EXIT_TEXT)
async def exit_dialog(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔚 Я поруч, коли захочеш продовжити.", reply_markup=menu)


# ================== MAIN CHAT ===================


@dialog_router.message(TarotChatFSM.chatting)
async def chat(message: types.Message, state: FSMContext):

    user_id = message.from_user.id
    text = message.text

    add_message(user_id, "user", text)

    # GPT answer
    response = await client.chat.completions.create(
        model="gpt-4.1-mini", messages=get_history(user_id), max_tokens=4000
    )

    reply = response.choices[0].message.content

    # ФІЛЬТР — GPT НЕ МАЄ ПРАВА НАЗИВАТИ КАРТИ ДО ТОГО, ЯК ЇХ НАДІСЛАВ БОТ
    if re.search(
        r"(Туз|Король|Королева|Лицар|Паж|Сонце|Місяць|Зірка|Башта|Імператриця|Імператор)",
        reply,
        re.IGNORECASE,
    ):
        if "Витягнуті карти:" not in reply:
            # Відповідь GPT залишаємо користувачу,
            # але НЕ додаємо в історію (щоб не зламати контекст)
            await message.answer(reply)
            return

    add_message(user_id, "assistant", reply)
    await message.answer(reply)

    # ========================
    # DETECT REAL CARD REQUESTS
    # ========================

    # GPT НЕ МАЄ ПРАВА НАЗИВАТИ КАРТИ, якщо бот не прислав карти
    CARD_WORDS = r"(Туз|Король|Королева|Лицар|Паж|Кубків|Жезлів|Мечів|Пентаклів|Сонце|Місяць|Зірка|Башта|Імператриця|Імператор|Колісниця|Відлюдник|Справедливість|Повішений|Суд|Світ)"

    if re.search(CARD_WORDS, reply, re.IGNORECASE):
        # якщо в повідомленні НІМАЄ "Витягнуті карти:", GPT збрехав → БЛОКУЄМО
        if "Витягнуті карти:" not in reply:
            # надсилаємо ОПИС БЕЗ КАРТ, але НЕ ДАЄМО йому в історію
            cleaned = re.sub(CARD_WORDS, "⚝", reply)
            await message.answer(cleaned)
            return

    # trigger = re.search(r"(витяг|тягн|дай|покаж|розклад|візьм)", reply, re.IGNORECASE)

    # need_1 = re.search(r"\b(1|одну)\s*карт", reply, re.IGNORECASE)
    # need_3 = re.search(r"\b(3|три)\s*карт", reply, re.IGNORECASE)
    # need_5 = re.search(r"\b(5|п’ять|пять)\s*карт", reply, re.IGNORECASE)

    # if not trigger:
    #     return

    # if not (need_1 or need_3 or need_5):
    #     return
    # ========================
    # SMART CARD REQUEST DETECTION
    # ========================

    # GPT каже, що сам бере карту → ми повинні витягнути
    trigger = re.search(
        r"(візьм(у|у)|візьму карту|я візьму|я беру|я відкрию|я відкрив|я витягнув|я витягну|я дістану|гляну карту|гляну карти|глянути карту|глянути карти|погляну карту|подивлюсь карту|подивлюсь карти|подивлюся карту|подивлюся карти|я готовий.*карт|я готовий.*глянут|готуюсь.*карт|готовий.*подивитись|готовий.*подивитися|розклад на|карта для тебе|карти для тебе)",
        reply,
        re.IGNORECASE
    )


    # Визначення кількості карт
    need_1 = re.search(r"(1|одну|одна|єдина)\s*карт", reply, re.IGNORECASE)
    need_3 = re.search(r"(3|три)\s*карт", reply, re.IGNORECASE)
    need_5 = re.search(r"(5|п’ять|пять)\s*карт", reply, re.IGNORECASE)

    # Якщо GPT каже, що він "берe карту", але не вказує кількість — беремо 1
    if trigger and not (need_1 or need_3 or need_5):
        amount = 1
    elif need_5:
        amount = 5
    elif need_3:
        amount = 3
    elif need_1:
        amount = 1
    else:
        return

    # ========================
    # HOW MANY CARDS?
    # ========================
    if need_5:
        amount = 5
    elif need_3:
        amount = 3
    else:
        amount = 1

    # ========================
    # DRAW CARDS
    # ========================
    cards = draw_cards(amount)

    # ========================
    # SEND CARDS TO USER
    # ========================
    await asyncio.sleep(0.3)

    if len(cards) == 1:
        c = cards[0]
        buf = load_img(c["image"], c["upright"])
        file = types.BufferedInputFile(buf.getvalue(), filename=f"{c['code']}.jpg")
        arrow = "⬆️" if c["upright"] else "⬇️"
        caption = f"{c['ua']} {arrow}"
        await message.answer_photo(photo=file, caption=caption)

    else:
        media = []
        for idx, c in enumerate(cards):
            buf = load_img(c["image"], c["upright"])
            file = types.BufferedInputFile(
                buf.getvalue(), filename=f"{c['code']}_{idx}.jpg"
            )
            arrow = "⬆️" if c["upright"] else "⬇️"
            caption = f"{c['ua']} {arrow}" if idx == 0 else None
            media.append(types.InputMediaPhoto(media=file, caption=caption))

        await message.answer_media_group(media)

    # ========================
    # SEND CARDS BACK TO GPT
    # ========================
    cards_text = "Витягнуті карти:\n" + "\n".join(
        f"{c['ua']} ({c['code']}) — {'пряма' if c['upright'] else 'перевернута'}"
        for c in cards
    )

    add_message(user_id, "user", cards_text)

    # SECOND GPT PASS — INTERPRETATION
    follow = await client.chat.completions.create(
        model="gpt-4.1-mini", messages=get_history(user_id), max_tokens=5000
    )

    final_reply = follow.choices[0].message.content
    add_message(user_id, "assistant", final_reply)

    await message.answer(final_reply)

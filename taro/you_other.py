import os
import json
import tempfile
import asyncio

from aiogram import Router, F, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from PIL import Image, ImageDraw, ImageFilter

from modules.menu import menu, build_main_menu
from cards_data import TAROT_CARDS
from openai import AsyncOpenAI
import config

from modules.user_stats_db import get_energy, change_energy


you_other = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#   ЕНЕРГІЯ
# ======================
ENERGY_COST_YOUOTHER = 2


async def charge_energy(user_id: int, cost: int):
    current = await get_energy(user_id)
    if current < cost:
        return False, current
    await change_energy(user_id, -cost)
    return True, current - cost


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_YOU_OTHER = """
Ти — досвідчений таролог-психолог.

Розклад "Ти — Інша людина" складається з 2 карт:
1 — Ти (емоції, наміри, очікування)
2 — Інша людина (її емоції, наміри, очікування)

Пиши тепло, емпатійно, без категоричних прогнозів.
Структура:
1) 🔮 Динаміка між вами
2) 🧩 Ти — розбір першої карти
3) 🧩 Інша людина — розбір другої карти
4) 🌙 Висновок
5) 💛 Порада
"""


# ======================
#      FSM STATES
# ======================
class YouOtherFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


# ======================
#   КОМБІНАЦІЯ 2 КАРТ
# ======================
def combine_you_other_cards(paths, uprights, background="background.png") -> str:

    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop(img):
        dpi = img.info.get("dpi", (300, 300))[0]
        px = int((1 * dpi) / 25.4)
        return img.crop((px, px, img.size[0]-px, img.size[1]-px))

    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
        result = Image.new("RGBA", img.size)
        result.paste(img, mask=mask)
        return result

    def add_shadow(img, offset=(12, 18), blur=32):
        w, h = img.size
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 160))
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.paste(shadow, offset, shadow)
        layer.paste(img, (0, 0), img)
        return layer

    cards = []
    for p, u in zip(paths, uprights):
        img = Image.open(p).convert("RGBA")
        img = crop(img)
        if not u:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = add_shadow(img)
        cards.append(img)

    cw = int(W * 0.26)
    ratio = cw / cards[0].size[0]
    ch = int(cards[0].size[1] * ratio)
    cards = [c.resize((cw, int(ch * 1.05)), Image.LANCZOS) for c in cards]

    spacing = int(W * 0.05)
    total_width = cw * 2 + spacing
    start_x = (W - total_width) // 2
    y = (H - ch) // 2

    for i, c in enumerate(cards):
        bg.alpha_composite(c, (start_x + i * (cw + spacing), y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG")
    return temp.name


# ======================
#  GPT
# ======================
async def interpret_you_other(question: str, cards_display: str) -> str:

    prompt = (
        f"{SYSTEM_PROMPT_YOU_OTHER}\n\n"
        f"Питання:\n{question}\n\n"
        f"Карти:\n{cards_display}\n\n"
        "Опиши динаміку між людьми чесно, м'яко, емпатійно."
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
    await state.clear()
    await state.set_state(YouOtherFSM.waiting_for_question)

    await message.answer(
        "❓ Про які стосунки або ситуацію між тобою і іншою людиною хочеш дізнатися?",
        reply_markup=ReplyKeyboardRemove(),
    )


# ======================
#       ПИТАННЯ
# ======================
@you_other.message(YouOtherFSM.waiting_for_question)
async def youother_question(message: types.Message, state: FSMContext):
    question = message.text.strip()
    await state.update_data(question=question)

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⚡ Обмінятись енергією ({ENERGY_COST_YOUOTHER}✨)",
                    callback_data="youother_pay"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню",
                    callback_data="youother_back"
                )
            ],
        ]
    )

    await message.answer(
        "✨ Щоб зробити розклад, потрібно обмінятись енергією.",
        reply_markup=kb,
    )

    await state.set_state(YouOtherFSM.waiting_for_energy)


# ======================
#  ОПЛАТА / НАЗАД
# ======================
@you_other.callback_query(YouOtherFSM.waiting_for_energy)
async def youother_energy_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # 🔙 Назад
    if data == "youother_back":
        try:
            await msg.delete()
        except:
            pass

        kb = build_main_menu(user_id)
        await callback.message.bot.send_message(
            msg.chat.id,
            "🔙 Повертаю в головне меню.",
            reply_markup=kb,
        )
        await state.clear()
        await callback.answer()
        return

    if data != "youother_pay":
        await callback.answer()
        return

    # Списання енергії
    ok, new_balance = await charge_energy(user_id, ENERGY_COST_YOUOTHER)
    if not ok:
        await msg.answer(
            f"🔋 Недостатньо енергії.\n"
            f"Потрібно: {ENERGY_COST_YOUOTHER}✨\n"
            f"У вас: {new_balance}✨"
        )
        return

    # Видаляємо старе
    try:
        await msg.delete()
    except:
        pass

    # Анімація
    anim = await callback.message.bot.send_message(
        msg.chat.id,
        "⚡ Обмінюємося енергією…"
    )
    try:
        for i in range(4):
            await anim.edit_text(f"⚡ Обмінюємося енергією… {'✨'*(i+1)}")
            await asyncio.sleep(0.5)
    except:
        pass

    try:
        await anim.delete()
    except:
        pass

    await callback.message.bot.send_message(
        msg.chat.id,
        f"✨ Обмін успішний!\nВаша енергія: <b>{new_balance}</b>✨",
        parse_mode="HTML",
    )

    # Кнопка WebApp
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

    await callback.message.bot.send_message(
        msg.chat.id,
        "🃏 Тепер оберіть 2 карти:",
        reply_markup=kb,
    )

    await state.set_state(YouOtherFSM.waiting_for_cards)
    await callback.answer()


# ======================
#      КАРТИ
# ======================
@you_other.message(YouOtherFSM.waiting_for_cards, F.web_app_data)
async def youother_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] YOU_OTHER WEBAPP:", data)

    chosen = data.get("chosen", [])
    if len(chosen) != 2:
        await message.answer("Для цього розкладу потрібно саме 2 карти.")
        return

    state_data = await state.get_data()
    question = state_data.get("question")

    img_paths = []
    uprights = []
    cards_display = []

    labels = ["(Ти)", "(Інша людина)"]

    for i, card in enumerate(chosen, start=1):
        info = TAROT_CARDS.get(card["name"])
        arrow = "⬆️" if card["upright"] else "⬇️"

        img_paths.append(info["image"])
        uprights.append(card["upright"])
        cards_display.append(f"{i}. {info['ua_name']} {arrow} {labels[i-1]}")

    final = combine_you_other_cards(img_paths, uprights)

    await message.answer_photo(
        FSInputFile(final),
        caption="🔮 Розклад: Ти — Інша людина",
    )

    load = await message.answer("🔮 Читаю, що між вами…")

    async def anim():
        i = 0
        while True:
            try:
                await load.edit_text("🔮 Читаю…\n" + "🔮"*((i%5)+1))
            except:
                break
            i += 1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    try:
        interpretation = await interpret_you_other(
            question, "\n".join(cards_display)
        )
    finally:
        task.cancel()
        try:
            await load.delete()
        except:
            pass

    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>👥 Розклад:</b> Ти — Інша людина\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    try:
        os.remove(final)
    except:
        pass

    await state.clear()

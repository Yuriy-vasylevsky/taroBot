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


horseshoe = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#   ENERGY CONFIG
# ======================
ENERGY_COST_HORSESHOE = 7


async def charge_energy_horseshoe(user_id: int, cost: int):
    current = await get_energy(user_id)
    if current < cost:
        return False, current

    await change_energy(user_id, -cost)
    return True, current - cost


# ======================
#    SYSTEM PROMPT
# ======================
SYSTEM_PROMPT_HORSESHOE = """
Ти — досвідчений таролог-наставник.

Розклад "Підкова" (7 карт) має такі позиції:
1 — Минуле
2 — Теперішнє
3 — Майбутнє
4 — Приховане
5 — Порада
6 — Зовнішній вплив
7 — Потенційний результат

Структура відповіді:
1) 🕰 Минуле
2) 🎯 Теперішнє
3) 🔮 Майбутнє
4) 👁️ Приховане
5) 🧭 Порада
6) 🌐 Зовнішній вплив
7) ⭐ Потенційний результат
8) 💛 Ключове послання розкладу
"""


# ======================
#      FSM STATES
# ======================
class HorseshoeFSM(StatesGroup):
    waiting_for_question = State()
    waiting_for_energy = State()
    waiting_for_cards = State()


# ======================
#   IMAGE BUILDER (7 карт)
# ======================
def combine_horseshoe_cards(paths, uprights, background="background.png") -> str:
    bg = Image.open(background).convert("RGBA")
    W, H = bg.size

    def crop(img):
        dpi = img.info.get("dpi", (300, 300))[0]
        px = int((1 * dpi) / 25.4)
        return img.crop((px, px, img.size[0] - px, img.size[1] - px))

    def round_corners(img, radius=45):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, *img.size], radius, fill=255)
        out = Image.new("RGBA", img.size)
        out.paste(img, mask=mask)
        return out

    def shadow(img, offset=(12, 18), blur=30):
        w, h = img.size
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]))
        layer.paste(sh, offset, sh)
        layer.paste(img, (0, 0), img)
        return layer

    cards = []
    for p, u in zip(paths, uprights):
        img = Image.open(p).convert("RGBA")
        img = crop(img)
        if not u:
            img = img.rotate(180, expand=True)
        img = round_corners(img)
        img = shadow(img)
        cards.append(img)

    card_w = int(W * 0.16)
    ratio = card_w / cards[0].width
    card_h = int(cards[0].height * ratio)

    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    positions = [
        (int(W * 0.18), int(H * 0.60)),
        (int(W * 0.12), int(H * 0.40)),
        (int(W * 0.28), int(H * 0.22)),
        (int(W * 0.50), int(H * 0.18)),
        (int(W * 0.72), int(H * 0.22)),
        (int(W * 0.84), int(H * 0.42)),
        (int(W * 0.50), int(H * 0.62)),
    ]

    for img, (x, y) in zip(cards, positions):
        bg.alpha_composite(img, (x, y))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(tmp.name)
    return tmp.name


# ======================
#   GPT INTERPRETATION
# ======================
async def interpret_horseshoe(question: str, cards_display: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT_HORSESHOE}\n\n"
        f"Питання: {question}\n\n"
        f"Карти:\n{cards_display}\n\n"
        f"Дай глибоке тлумачення."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_HORSESHOE},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#       КНОПКА
# ======================
@horseshoe.message(F.text == "🍀 Підкова (7 карт)")
async def horseshoe_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(HorseshoeFSM.waiting_for_question)

    await message.answer(
        "❓ Сформулюй питання для розкладу «Підкова» (7 карт).",
        reply_markup=ReplyKeyboardRemove(),
    )


# ======================
#       ПИТАННЯ
# ======================
@horseshoe.message(HorseshoeFSM.waiting_for_question)
async def horseshoe_question(message: types.Message, state: FSMContext):
    q = (message.text or "").strip()
    if not q:
        await message.answer("Напиши питання 🙏")
        return

    await state.update_data(question=q)

    # кнопки обміну енергією
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⚡ Обмінятись енергією ({ENERGY_COST_HORSESHOE}✨)",
                    callback_data="hs_pay",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="⬅️ Повернутись в меню",
                    callback_data="hs_back",
                )
            ],
        ]
    )

    await message.answer(
        "✨ Щоб виконати розклад, потрібно обмінятись енергією.",
        reply_markup=kb,
    )

    await state.set_state(HorseshoeFSM.waiting_for_energy)


# ======================
#   ОПЛАТА ЕНЕРГІЄЮ
# ======================
@horseshoe.callback_query(HorseshoeFSM.waiting_for_energy)
async def horseshoe_energy(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id
    msg = callback.message

    # вихід
    if data == "hs_back":
        try:
            await msg.delete()
        except:
            pass

        kb = build_main_menu(user_id)
        await callback.message.bot.send_message(
            msg.chat.id, "🔙 Повертаю в меню.", reply_markup=kb
        )
        await state.clear()
        await callback.answer()
        return

    if data != "hs_pay":
        await callback.answer()
        return

    await callback.answer()

    # списання енергії
    ok, value = await charge_energy_horseshoe(user_id, ENERGY_COST_HORSESHOE)
    if not ok:
        await msg.answer(
            f"🔋 Недостатньо енергії.\nПотрібно: {ENERGY_COST_HORSESHOE}✨\n"
            f"У вас: {value}✨"
        )
        return

    try:
        await msg.delete()
    except:
        pass

    # анімація 2 сек
    anim_msg = await callback.message.bot.send_message(
        msg.chat.id, "⚡ Обмінюємося енергією…"
    )

    for i in range(4):
        try:
            await anim_msg.edit_text(f"⚡ Обмінюємося енергією… {'✨'*(i+1)}")
        except:
            break
        await asyncio.sleep(0.5)

    try:
        await anim_msg.delete()
    except:
        pass

    # підтвердження
    await callback.message.bot.send_message(
        msg.chat.id,
        f"⚡ Обмін успішний!\nЕнергія: <b>{value}</b> ✨",
        parse_mode="HTML",
    )

    # кнопка вибору карт
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                types.KeyboardButton(
                    text="✨ Обрати 7 карт",
                    web_app=types.WebAppInfo(
                        url="https://yuriy-vasylevsky.github.io/web7cards"
                    ),
                )
            ]
        ],
    )

    await callback.message.bot.send_message(
        msg.chat.id, "🃏 Оберіть 7 карт:", reply_markup=kb
    )

    await state.set_state(HorseshoeFSM.waiting_for_cards)


# ======================
#      WEBAPP CARDS
# ======================
@horseshoe.message(HorseshoeFSM.waiting_for_cards, F.web_app_data)
async def horseshoe_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)

    if data.get("action") != "seven_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 7:
        await message.answer("Потрібно саме 7 карт 🙏")
        return

    state_data = await state.get_data()
    question = state_data.get("question")

    img_paths = []
    uprights = []
    cards_display = []

    labels = [
        "Минуле",
        "Теперішнє",
        "Майбутнє",
        "Приховане",
        "Порада",
        "Зовнішній вплив",
        "Потенційний результат",
    ]

    for i, card in enumerate(chosen, start=1):
        name = card["name"]
        up = card["upright"]
        info = TAROT_CARDS.get(name)
        img_paths.append(info["image"])
        uprights.append(up)

        ua = info["ua_name"]
        arrow = "⬆️" if up else "⬇️"
        cards_display.append(f"{i}. {ua} {arrow} — {labels[i-1]}")

    final_img = combine_horseshoe_cards(img_paths, uprights)

    await message.answer_photo(
        FSInputFile(final_img),
        caption="🔮 Розклад: Підкова",
    )

    # анімація GPT
    load = await message.answer("🔮 Читаю розклад…")

    async def anim():
        i = 0
        while True:
            try:
                await load.edit_text("🔮 Читаю розклад…\n" + "🔮" * ((i % 5) + 1))
            except:
                break
            i += 1
            await asyncio.sleep(0.25)

    task = asyncio.create_task(anim())

    try:
        interpretation = await interpret_horseshoe(question, "\n".join(cards_display))
    finally:
        task.cancel()
        try: await load.delete()
        except: pass

    await message.answer(
        f"<b>❓ Питання:</b> {question}\n\n"
        f"<b>🍀 Розклад Підкова:</b>\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{interpretation}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    try:
        os.remove(final_img)
    except:
        pass

    await state.clear()

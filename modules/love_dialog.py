import os
import json
import tempfile
import asyncio

from PIL import Image, ImageDraw, ImageFilter
from aiogram import Router, F, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from modules.menu import menu
from cards_data import TAROT_CARDS

from openai import AsyncOpenAI
import config


love_taro = Router()
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


# ======================
#   SYSTEM PROMPT (ЛЮБОВ)
# ======================
SYSTEM_PROMPT_LOVE = """
Ти — досвідчений таролог, який спеціалізується на темі кохання і стосунків.
Говори м'яко, підтримуюче, але чесно.
Поважай особисті кордони, не давай категоричних обіцянок ("назавжди", "гарантовано").
Не лякай, не маніпулюй, не засуджуй. Підкреслюй цінність людини незалежно від партнера.
Пиши українською або російською — так, як до тебе звертаються.

Розклад робиться не "взагалі", а про конкретний зв'язок / людину, яку користувач позначає ім'ям або описом
(наприклад, "Олег", "чоловік", "колишня", "дівчина з роботи", "людина з побачень").

Структура відповіді:
1) ❤️ Загальний настрій / тема стосунків
2) 👁 Розбір кожної карти по позиціях розкладу
3) 🌙 Висновок про стосунки
4) 💌 Порада серцю
"""


# ======================
#   FSM СТАНИ
# ======================
class LoveDialog(StatesGroup):
    choosing_layout = State()
    waiting_for_target = State()   # ім'я / опис людини або зв'язку
    waiting_for_cards = State()


# ======================
#   ЛЮБОВНІ РОЗКЛАДИ (3 карти)
# ======================
LOVE_LAYOUTS = {
    "love_you_partner_between": {
        "name": "Ти — Партнер — Що між вами",
        "positions": [
            "Ти зараз у цих стосунках",
            "Партнер зараз",
            "Енергія між вами / що між вами",
        ],
    },
    "love_perspective": {
        "name": "Перспектива стосунків",
        "positions": [
            "Поточний стан стосунків",
            "Що допомагає / що варто підсилити",
            "Ймовірний розвиток / перспектива",
        ],
    },
    "love_new": {
        "name": "Нові стосунки / Знайомство",
        "positions": [
            "Що ти зараз притягуєш у коханні",
            "Що блокує або заважає любові",
            "Як відкритися новим здоровим стосункам",
        ],
    },
}


# ======================
#   КОМБІНУВАТИ 3 КАРТИ + ФОН
# ======================
def combine_three_cards_with_background(
    paths, uprights, background_path: str = "background.png"
) -> str:
    """
    Об'єднує 3 карти на PNG-фоні:
    - трохи обрізає поля
    - округлює кути
    - додає 3D-тінь (ефект підняття)
    - ідеально центрує на фоні
    Повертає шлях до тимчасового PNG.
    """

    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size

    # Обрізання ~1 мм (якщо є DPI)
    def crop_1mm(img: Image.Image) -> Image.Image:
        dpi = img.info.get("dpi", (300, 300))[0]
        mm_to_px = dpi / 25.4
        px = int(1 * mm_to_px)
        w, h = img.size
        if px <= 0 or px * 2 >= min(w, h):
            return img
        return img.crop((px, px, w - px, h - px))

    # Заокруглення
    def round_corners(img: Image.Image, radius: int = 45) -> Image.Image:
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius, fill=255)
        rounded = Image.new("RGBA", img.size)
        rounded.paste(img, (0, 0), mask)
        return rounded

    # Тінь
    def add_3d_shadow(
        img: Image.Image,
        offset=(12, 18),
        blur: int = 38,
        shadow_opacity: int = 140,
        corner_radius: int = 45,
    ) -> Image.Image:
        w, h = img.size

        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), corner_radius, fill=shadow_opacity)

        shadow.paste((0, 0, 0, shadow_opacity), (0, 0), mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

        layer = Image.new("RGBA", (w + offset[0], h + offset[1]), (0, 0, 0, 0))
        layer.alpha_composite(shadow, offset)
        layer.alpha_composite(img, (0, 0))
        return layer

    cards = []
    for path, up in zip(paths, uprights):
        img = Image.open(path).convert("RGBA")
        img = crop_1mm(img)

        if not up:
            img = img.rotate(180, expand=True)

        img = round_corners(img)
        img = add_3d_shadow(img)
        cards.append(img)

    # Масштаб
    card_w = int(W * 0.27)
    ratio = card_w / cards[0].size[0]
    card_h = int(cards[0].size[1] * ratio)
    cards = [c.resize((card_w, int(card_h * 1.05)), Image.LANCZOS) for c in cards]

    # Центрування
    spacing = int(W * 0.03)
    total_width = card_w * 3 + spacing * 2
    start_x = int((W - total_width) / 2)
    y = int((H - card_h) / 2)

    x_positions = [
        start_x,
        start_x + card_w + spacing,
        start_x + (card_w + spacing) * 2,
    ]

    for img, x in zip(cards, x_positions):
        bg.alpha_composite(img, (x, y))

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    bg.save(temp.name, "PNG", quality=95)
    return temp.name


# ======================
#   GPT: ЛЮБОВНЕ ТЛУМАЧЕННЯ
# ======================
async def interpret_love_cards_gpt(
    target_name: str,
    cards_display: str,
    layout: dict,
) -> str:
    """
    layout: {
      "name": "...",
      "positions": ["...", "...", "..."]
    }
    target_name — ім'я / опис людини, на яку спрямовано розклад
    """

    target_name_clean = target_name.strip() or "ця людина / цей зв'язок"

    layout_block = (
        f"Обраний любовний розклад:\n{layout['name']}\n"
        f"Позиції карт:\n"
        f"1 — {layout['positions'][0]}\n"
        f"2 — {layout['positions'][1]}\n"
        f"3 — {layout['positions'][2]}\n"
    )

    prompt = (
        f"{SYSTEM_PROMPT_LOVE}\n\n"
        f"Тема: кохання / стосунки.\n"
        f"Розклад робиться про зв'язок між людиною, яка питає, та: «{target_name_clean}».\n"
        f"Не вигадуй конкретних фактів (дат, професій, подій), а працюй з енергією стосунків.\n\n"
        f"{layout_block}\n"
        f"Витягнуті карти (з позиціями):\n{cards_display}\n\n"
        f"Дай глибоке тлумачення, враховуючи любовну тематику, позиції розкладу і те, "
        f"що це саме стосунки з «{target_name_clean}»."
    )

    resp = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_LOVE},
            {"role": "user", "content": prompt},
        ],
        max_tokens=900,
        temperature=0.9,
    )

    return resp.choices[0].message.content


# ======================
#   СТАРТ: "❤️ Любов / Стосунки"
# ======================
@love_taro.message(F.text == "❤️ Любов / Стосунки")
async def love_dialog_start(message: types.Message, state: FSMContext):
    """
    1) показуємо інлайн-кнопки вибору типу любовного розкладу
    """
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="💑 Ти — Партнер — Що між вами",
                    callback_data="love_you_partner_between",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔮 Перспектива стосунків",
                    callback_data="love_perspective",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="✨ Нові стосунки / Знайомство",
                    callback_data="love_new",
                )
            ],
        ]
    )

    await state.clear()
    await state.set_state(LoveDialog.choosing_layout)
    await message.answer("❤️ Обери любовний розклад:", reply_markup=kb)


# ======================
#   ОБРАННЯ ЛЮБОВНОГО РОЗКЛАДУ
# ======================
@love_taro.callback_query(LoveDialog.choosing_layout)
async def love_choose_layout(callback: types.CallbackQuery, state: FSMContext):
    layout_key = callback.data
    layout = LOVE_LAYOUTS.get(layout_key)

    if not layout:
        await callback.answer("Невідомий розклад.", show_alert=True)
        return

    await state.update_data(layout=layout)

    await callback.message.answer(
        f"❤️ Обрано розклад: <b>{layout['name']}</b>\n\n"
        "Тепер напиши ім'я або коротке позначення людини, "
        "на яку спрямований цей розклад (наприклад, «Олег», «чоловік», «колишня», "
        "«дівчина з роботи», «людина з побачень»):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )

    await state.set_state(LoveDialog.waiting_for_target)
    await callback.answer()


# ======================
#   ІМ'Я / ПОЗНАЧЕННЯ ЛЮДИНИ
# ======================
@love_taro.message(LoveDialog.waiting_for_target)
async def love_target(message: types.Message, state: FSMContext):
    target_name = (message.text or "").strip()
    if not target_name:
        await message.answer(
            "Будь ласка, напиши хоча б якось, як ти позначаєш цю людину 🙏\n"
            "Наприклад: «Олег», «колишня», «партнер», «дівчина з роботи»."
        )
        return

    await state.update_data(target_name=target_name)

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

    await message.answer(
        "🃏 Чудово. Тепер обери 3 карти через колоду нижче:", reply_markup=kb
    )

    await state.set_state(LoveDialog.waiting_for_cards)


# ======================
#   3 КАРТИ з WebApp
# ======================
@love_taro.message(LoveDialog.waiting_for_cards, F.web_app_data)
async def love_cards(message: types.Message, state: FSMContext):
    data = json.loads(message.web_app_data.data)
    print("[DEBUG] LOVE WEBAPP:", data)

    if data.get("action") != "three_cards":
        return

    chosen = data.get("chosen", [])
    if len(chosen) != 3:
        await message.answer("Для цього розкладу потрібно саме 3 карти.")
        return

    state_data = await state.get_data()
    layout = state_data.get("layout")
    target_name = state_data.get("target_name", "").strip() or "ця людина / цей зв'язок"

    if not layout:
        await message.answer("Щось пішло не так. Спробуй почати любовний розклад заново.")
        await state.clear()
        return

    img_paths: list[str] = []
    uprights: list[bool] = []
    cards_display: list[str] = []

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
        pos_name = layout["positions"][i - 1]
        cards_display.append(f"{i}. {ua} {arrow} — {pos_name}")

    if len(img_paths) != 3:
        await message.answer("Не вдалося завантажити всі три карти.")
        await state.clear()
        return

    # 1️⃣ Комбінуємо 3 карти в одне зображення
    final_img = combine_three_cards_with_background(
        img_paths,
        uprights,
        background_path="background.png",  # твій PNG-фон
    )

    await message.answer_photo(
        FSInputFile(final_img),
        caption=f"❤️ Любовний розклад: {layout['name']}\n"
                f"👤 Для: {target_name}",
    )

    # 2️⃣ Анімація "тлумачення…"
    load_msg = await message.answer("🔮 Читаю твій любовний розклад…")

    async def anim():
        i = 0
        while True:
            try:
                await load_msg.edit_text(
                    "🔮 Читаю твій любовний розклад…\n" + "🔮" * ((i % 5) + 1)
                )
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.25)

    anim_task = asyncio.create_task(anim())

    # 3️⃣ GPT-інтерпретація
    try:
        text = await interpret_love_cards_gpt(
            target_name,
            "\n".join(cards_display),
            layout,
        )
    finally:
        anim_task.cancel()
        try:
            await load_msg.delete()
        except Exception:
            pass

    # 4️⃣ Відповідь користувачу
    await message.answer(
        f"<b>👤 Для кого розклад:</b> {target_name}\n\n"
        f"<b>❤️ Любовний розклад:</b> {layout['name']}\n"
        f"{chr(10).join(cards_display)}\n\n"
        f"{text}",
        parse_mode="HTML",
        reply_markup=menu,
    )

    # Чистимо тимчасовий файл
    try:
        os.remove(final_img)
    except Exception:
        pass

    await state.clear()

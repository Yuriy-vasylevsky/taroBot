import os
import uuid
import shutil
import random
import tempfile
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from PIL import Image
import config
from cards_data import TAROT_CARDS  # 🔮 база карт

# =============================
# ⚙️ Ініціалізація
# =============================
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# =============================
# 🧭 Меню
# =============================
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🃏 Карта дня")]],
    resize_keyboard=True,
)


# =============================
# 🪄 Запит до n8n (GPT-тлумачення)
# =============================
async def get_interpretation_from_n8n(
    cards: list[str], spread_type: str, username: str
):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            config.N8N_WEBHOOK_URL,
            json={"cards": cards, "spread": spread_type, "user": username},
        ) as resp:
            try:
                data = await resp.json()
                if isinstance(data, list):
                    data = data[0]
                return data.get("interpretation", "⚠️ Не вдалося отримати тлумачення.")
            except Exception as e:
                print(f"[ERROR] N8N response error: {e}")
                return "⚠️ Виникла помилка при обробці відповіді від n8n."


# =============================
# 🎴 Витяг карти
# =============================
def draw_card():
    """Випадково вибирає карту (upright / reversed)."""
    card_name = random.choice(list(TAROT_CARDS.keys()))
    position = "reversed" if random.random() < 0.5 else "upright"
    card = TAROT_CARDS[card_name]

    meaning = card[f"meaning_{position}"]
    ua_name = card["ua_name"]
    image_path = card["image"]
    orientation_ua = "⬆️" if position == "upright" else "⬇️"

    print(f"[DEBUG] {card_name} → {position} → {image_path}")
    return card_name, ua_name, position, orientation_ua, meaning, image_path


# =============================
# 🧙 Команди
# =============================
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "🔮 Вітаю у Таро-боті!\n"
        "Обери розклад, щоб дізнатись, що карти кажуть сьогодні...",
        reply_markup=menu,
    )


@dp.message(F.text == "🃏 Карта дня")
async def card_of_the_day(message: types.Message):
    card_name, ua_name, position, orientation_ua, meaning, image_path = draw_card()

    # 🪄 створюємо тимчасовий файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        tmp_path = tmp_file.name

    try:
        # 📸 відкриваємо і обертаємо, якщо треба
        img = Image.open(image_path).convert("RGB")
        if position == "reversed":
            img = img.transpose(Image.ROTATE_180)
        img.save(tmp_path, format="JPEG", quality=95)

        # 📤 надсилаємо
        photo = FSInputFile(tmp_path, filename=f"{uuid.uuid4().hex}.jpg")
        caption = f"<b>{ua_name}</b> ({orientation_ua})\n\n{meaning}"
        await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")

    finally:
        try:
            os.remove(tmp_path)
        except Exception as e:
            print(f"[WARN] Не вдалося видалити тимчасовий файл: {e}")

    # 🤖 (опціонально) GPT-тлумачення
    interpretation = await get_interpretation_from_n8n(
        [f"{ua_name} ({orientation_ua})"],
        "card_of_the_day",
        message.from_user.full_name,
    )
    await message.answer(interpretation)


# =============================
# 🚀 Запуск
# =============================
async def main():
    print("🔮 Бот запущено...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


from aiogram import Router, types, F
from aiogram.filters import CommandStart
from modules.menu import menu
from modules.user_stats_db import (
    track_user_activity,
    add_referral,
    get_referrer,
    reward_referral,
)

start_router = Router()


@start_router.message(CommandStart())
async def start_cmd(message: types.Message):
    user = message.from_user
    user_id = user.id
    username = user.username
    full_name = user.full_name

    # лог активності
    await track_user_activity(user_id, username, full_name, "start")

    # обробка реферального коду
    args = message.text.split()
    referrer_id = None

    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except:
            referrer_id = None

    # ---- РЕФЕРАЛКА ----
    if referrer_id and referrer_id != user_id:

        already = await get_referrer(user_id)
        if not already:
            await add_referral(user_id, referrer_id)

            rewarded = await reward_referral(referrer_id)
            if rewarded:
                try:
                    await message.bot.send_message(
                        referrer_id,
                        "🎉 Ви отримали <b>+12 бананів 🍌</b> за запрошеного друга!",
                        parse_mode="HTML"
                    )
                except:
                    pass

    # --- ГОЛОВНЕ МЕНЮ ---
    photo_path = "assets/2.png"
    kb = menu

    try:
        await message.answer_photo(
            photo=types.FSInputFile(photo_path),
            caption=f"👋 Привіт, <b>{full_name}</b>!\nРадий тебе бачити 💛",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except FileNotFoundError:
        # Fallback якщо фото не знайдено
        await message.answer(
            f"👋 Привіт, <b>{full_name}</b>!\nРадий тебе бачити 💛",
            reply_markup=kb,
            parse_mode="HTML",
        )

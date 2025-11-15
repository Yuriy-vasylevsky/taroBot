

# import asyncio
# from aiogram import types


# async def run_animation(
#     message: types.Message,
#     text: str = "✨ Звертаюся до вищих сил...",
#     emoji: str = "🍌",
#     total_segments: int = 10,
#     speed: float = 0.6,
#     final_text: str | None = None,
#     extra_texts: list[str] | None = None,
# ):
#     """
#     Універсальна анімація прогрес-бару з автоочищенням і змінним текстом.
#     extra_texts — список додаткових фраз, які циклічно змінюються під час анімації.
#     """
#     loading = await message.answer(
#         f"{text}\n\n[{'▒' * total_segments}] 0%", parse_mode="HTML"
#     )

#     progress_bar = ["▒"] * total_segments
#     i = 0
#     phrase_index = 0
#     if not extra_texts:
#         extra_texts = [text]

#     while i < total_segments:
#         await asyncio.sleep(speed)
#         progress_bar[i] = emoji
#         i += 1
#         percent = int((i / total_segments) * 100)

#         # змінюємо текст фрази
#         phrase = extra_texts[phrase_index % len(extra_texts)]
#         phrase_index += 1

#         text_now = f"{phrase}\n\n[{''.join(progress_bar)}] {percent}%"
#         try:
#             await loading.edit_text(text_now, parse_mode="HTML")
#         except Exception as e:
#             if "message is not modified" not in str(e):
#                 print(f"[WARN] edit_text: {e}")

#     final_text = final_text or f"🌕 Енергії проявилися!\n\n[{emoji * total_segments}] 100%"
#     try:
#         await loading.edit_text(final_text, parse_mode="HTML")
#     except Exception:
#         pass

#     await asyncio.sleep(1.2)
#     try:
#         await message.bot.delete_message(
#             chat_id=message.chat.id, message_id=loading.message_id
#         )
#     except Exception:
#         pass
import asyncio
from aiogram import types


async def run_animation(
    message: types.Message,
    text: str = "✨ Звертаюся до вищих сил...",
    emoji: str = "🍌",
    total_segments: int = 10,
    speed: float = 0.6,
    final_text: str | None = None,
    extra_texts: list[str] | None = None,
):
    """
    Анімація прогрес-бару з плавним оновленням і зміною фраз один раз.
    extra_texts — список текстів, які відображаються по черзі лише один цикл.
    """
    loading = await message.answer(
        f"{text}\n\n[{'▒' * total_segments}] 0%", parse_mode="HTML"
    )

    progress_bar = ["▒"] * total_segments
    total_steps = total_segments
    total_phrases = len(extra_texts) if extra_texts else 1
    phrase_interval = max(1, total_steps // total_phrases)
    phrase_index = 0

    for i in range(total_steps):
        await asyncio.sleep(speed)
        progress_bar[i] = emoji
        percent = int(((i + 1) / total_steps) * 100)

        # змінюємо фразу лише тоді, коли настав момент
        if extra_texts and (i // phrase_interval) < len(extra_texts):
            phrase_index = i // phrase_interval
            phrase = extra_texts[phrase_index]
        else:
            phrase = extra_texts[-1] if extra_texts else text

        new_text = f"{phrase}\n\n[{''.join(progress_bar)}] {percent}%"
        try:
            await loading.edit_text(new_text, parse_mode="HTML")
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"[WARN] edit_text: {e}")

    # фінальний текст
    final_text = final_text or f"🌕 Тлумачення готове!\n\n[{emoji * total_segments}] 100%"
    try:
        await loading.edit_text(final_text, parse_mode="HTML")
    except Exception:
        pass

    await asyncio.sleep(1.2)
    try:
        await message.bot.delete_message(
            chat_id=message.chat.id, message_id=loading.message_id
        )
    except Exception:
        pass

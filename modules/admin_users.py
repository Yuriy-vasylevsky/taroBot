from math import ceil
from datetime import datetime, timedelta

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.user_stats_db import (
    get_users_with_last_activity_and_actions,
    get_users_count,
    change_energy,
    get_energy,
)
import config

admin_users_router = Router()
ADMIN_ID = config.ADMIN_ID

USERS_PER_PAGE = 5  # скільки юзерів на сторінку


# ============================================================
# Формат "сьогодні / вчора / дата"
# ============================================================
def _format_last_active(last_active: str | None) -> str:
    if not last_active:
        return "немає даних"

    try:
        dt = datetime.fromisoformat(last_active)
    except ValueError:
        return last_active

    now = datetime.now()
    today = now.date()
    date = dt.date()
    time_part = dt.strftime("%H:%M")

    if date == today:
        return f"сьогодні о {time_part}"
    elif date == today - timedelta(days=1):
        return f"вчора о {time_part}"
    else:
        months = [
            "січня", "лютого", "березня", "квітня",
            "травня", "червня", "липня", "серпня",
            "вересня", "жовтня", "листопада", "грудня",
        ]
        return f"{dt.day} {months[dt.month - 1]} о {time_part}"


# ============================================================
# Завантаження сторінки
# ============================================================
async def _load_users_page(page: int):
    total_users = await get_users_count()
    if total_users == 0:
        return [], 1, 1

    total_pages = max(1, ceil(total_users / USERS_PER_PAGE))
    page = max(1, min(page, total_pages))

    offset = (page - 1) * USERS_PER_PAGE

    users = await get_users_with_last_activity_and_actions(
        limit_users=USERS_PER_PAGE,
        actions_per_user=10,   # скільки дій підтягуємо
        offset=offset,
    )

    return users, page, total_pages


def _short_name(u: dict) -> str:
    fname = (u.get("full_name") or "").strip()
    uname = (u.get("username") or "").strip()

    if fname:
        return fname
    if uname:
        return f"@{uname}"
    return str(u.get("user_id"))


# ============================================================
# Текст списку
# ============================================================
def _build_list_text(page: int, total_pages: int) -> str:
    return (
        "⚡ <b>Енергія користувачів</b>\n"
        f"Сторінка {page} з {total_pages}\n\n"
        "Натисни на ім’я, щоб відкрити картку користувача."
    )


# ============================================================
# Клавіатура списку
# ============================================================
def _build_list_keyboard(
    users: list[dict],
    page: int,
    total_pages: int
) -> InlineKeyboardMarkup:

    rows: list[list[InlineKeyboardButton]] = []

    for u in users:
        rows.append([
            InlineKeyboardButton(
                text=f"{_short_name(u)} • {_format_last_active(u['last_active_at'])}",
                callback_data=f"au_open:{u['user_id']}:{page}",
            )
        ])

    # пагінація
    pag_row: list[InlineKeyboardButton] = []

    if page > 1:
        pag_row.append(
            InlineKeyboardButton(
                text="⬅️ Попередня",
                callback_data=f"au_list:{page-1}",
            )
        )

    pag_row.append(
        InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="au_noop",
        )
    )

    if page < total_pages:
        pag_row.append(
            InlineKeyboardButton(
                text="Наступна ➡️",
                callback_data=f"au_list:{page+1}",
            )
        )

    rows.append(pag_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
# Чистка дій — тільки те, що ПИСАВ юзер
# ============================================================
def _clean_actions(actions: list[str] | None) -> list[str]:
    """
    Використовуємо твою стару схему:
    - "Натиснув / написав: ..."  -> це залишаємо (повідомлення/команди)
    - "Inline-кнопка: ..."       -> повністю ігноруємо (кліки по кнопках)
    """
    if not actions:
        return []

    result: list[str] = []

    for a in actions:
        if a.startswith("Inline-кнопка:"):
            # кліки по кнопках не показуємо
            continue

        # забираємо службовий префікс, лишаємо тільки те, що писав
        if a.startswith("Натиснув / написав: "):
            a = a.replace("Натиснув / написав: ", "", 1)

        # якщо після всього є хоч щось — додаємо
        a = a.strip()
        if a:
            result.append(a)

    return result


# ============================================================
# Текст картки користувача
# ============================================================
def _build_user_card_text(u: dict) -> str:
    uid = u["user_id"]
    uname = u["username"]
    fname = u["full_name"] or "—"
    energy = u["energy"]
    last = _format_last_active(u["last_active_at"])

    if uname:
        profile_link = f'<a href="tg://user?id={uid}">@{uname}</a>'
    else:
        profile_link = f'<a href="tg://user?id={uid}">{fname}</a>'

    clean_actions = _clean_actions(u["actions"])

    if clean_actions:
        # нумерація + ❤️
        actions_block_lines = [
            f"{idx}. ❤️ {text}"
            for idx, text in enumerate(clean_actions, start=1)
        ]
        actions_block = "\n".join(actions_block_lines)
    else:
        actions_block = "• (користувач ще нічого не писав боту)"

    text = (
        f"👤 <b>{fname}</b>\n"
        f"🔗 Профіль: {profile_link}\n"
        f"🆔 <code>{uid}</code>\n"
        f"🔋 Енергія: <b>{energy}</b> ✨\n"
        f"🕒 Активність: {last}\n\n"
        f"📨 <b>Дії користувача:</b>\n{actions_block}"
    )

    return text


# ============================================================
# Кнопки картки
# ============================================================
def _build_user_card_kb(user_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ 3 ✨",
                    callback_data=f"au_add:{user_id}:3:{page}",
                ),
                InlineKeyboardButton(
                    text="➕ 12 ✨",
                    callback_data=f"au_add:{user_id}:12:{page}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"au_list:{page}",
                )
            ],
        ]
    )


# ============================================================
# Всі користувачі — вхідна кнопка
# ============================================================
@admin_users_router.message(F.text == "⚡ Енергія користувачів")
async def show_users_energy(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users, page, total_pages = await _load_users_page(1)

    if not users:
        await message.answer("Поки що немає збережених користувачів.")
        return

    text = _build_list_text(page, total_pages)
    kb = _build_list_keyboard(users, page, total_pages)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ============================================================
# Пагінація списку
# ============================================================
@admin_users_router.callback_query(F.data.startswith("au_list:"))
async def users_list_page(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Немає доступу.", show_alert=True)
        return

    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer()
        return

    users, page, total_pages = await _load_users_page(page)

    text = _build_list_text(page, total_pages)
    kb = _build_list_keyboard(users, page, total_pages)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await callback.answer()


@admin_users_router.callback_query(F.data == "au_noop")
async def users_noop(callback: types.CallbackQuery):
    await callback.answer()


# ============================================================
# Відкрити картку користувача
# ============================================================
@admin_users_router.callback_query(F.data.startswith("au_open:"))
async def open_user_card(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Немає доступу.", show_alert=True)
        return

    try:
        _, uid_str, page_str = callback.data.split(":")
        user_id = int(uid_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Помилка даних.", show_alert=True)
        return

    users, _, _ = await _load_users_page(page)
    target = next((u for u in users if u["user_id"] == user_id), None)

    if not target:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    text = _build_user_card_text(target)
    kb = _build_user_card_kb(user_id, page)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await callback.answer()


# ============================================================
# Нарахувати енергію
# ============================================================
@admin_users_router.callback_query(F.data.startswith("au_add:"))
async def add_energy(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Немає доступу.", show_alert=True)
        return

    try:
        _, uid_str, amount_str, page_str = callback.data.split(":")
        user_id = int(uid_str)
        amount = int(amount_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Помилка даних.", show_alert=True)
        return

    await change_energy(user_id, amount)
    new_energy = await get_energy(user_id)

    await callback.answer(
        f"✨ Додано {amount}. Нова енергія: {new_energy}",
        show_alert=True,
    )

    users, _, _ = await _load_users_page(page)
    target = next((u for u in users if u["user_id"] == user_id), None)

    if not target:
        return

    target["energy"] = new_energy
    text = _build_user_card_text(target)
    kb = _build_user_card_kb(user_id, page)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

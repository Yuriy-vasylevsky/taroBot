
from datetime import datetime, timedelta
from math import ceil

import config
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from modules.menu import admin_menu
from modules.user_stats_db import (
    get_users_with_last_activity_and_actions,
    get_users_count,
)

admin_router = Router()
ADMIN_ID = config.ADMIN_ID

USERS_PER_PAGE = 5

print(f"🔧 ADMIN_PANEL завантажено | ADMIN_ID = {ADMIN_ID} (тип: {type(ADMIN_ID)})")

# =============== ХЕЛПЕРИ ===============
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
        months = ["січня","лютого","березня","квітня","травня","червня","липня","серпня","вересня","жовтня","листопада","грудня"]
        return f"{dt.day} {months[dt.month-1]} о {time_part}"


def _build_users_pagination_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Попередня", callback_data=f"admin_users:page:{page-1}"))
    buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="admin_users:noop"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="Наступна ➡️", callback_data=f"admin_users:page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


async def _render_users_page(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Будує текст + клавіатуру для сторінки користувачів"""
    total_users = await get_users_count()
    if total_users == 0:
        return "Поки що немає збережених користувачів.", None

    total_pages = max(1, ceil(total_users / USERS_PER_PAGE))
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    offset = (page - 1) * USERS_PER_PAGE

    users = await get_users_with_last_activity_and_actions(
        limit_users=USERS_PER_PAGE,
        actions_per_user=5,
        offset=offset,
    )

    lines = [
        f"👥 <b>Список користувачів</b>",
        f"Сторінка {page} з {total_pages}",
        "",
    ]

    if not users:
        lines.append("На цій сторінці користувачів немає.")
        kb = _build_users_pagination_kb(page, total_pages)
        return "\n".join(lines), kb

    for idx, u in enumerate(users, start=offset + 1):
        uid = u["user_id"]
        uname = f"@{u['username']}" if u["username"] else "—"
        fname = u["full_name"] or "—"
        energy = u["energy"]
        last_active = _format_last_active(u["last_active_at"])
        actions = u["actions"] or []

        clean_actions = []
        for a in actions:
            a = a.replace("Натиснув / написав: ", "", 1)
            a = a.replace("Inline-кнопка: ", "", 1)
            clean_actions.append(a)

        actions_lines = "\n".join(f"🔹 {a}" for a in clean_actions) if clean_actions else "🔸 (немає дій)"

        block = (
            f"<b>#{idx}.</b> 👤 {fname} {uname}\n"
            f"🆔 <code>{uid}</code>\n"
            f"🔋 Енергія: <b>{energy}</b>\n"
            f"🕒 Активність: {last_active}\n"
            f"📜 Останні дії:\n{actions_lines}\n"
        )
        lines.append(block)

    text = "\n".join(lines)
    kb = _build_users_pagination_kb(page, total_pages)
    return text, kb


# =============== ХЕНДЛЕРИ ===============

@admin_router.message(F.text.in_({"🛠 Адмін-панель", "/admin"}))
async def open_admin_panel(message: types.Message):
    print(f"👤 Спроба входу в адмін | user_id={message.from_user.id} | ADMIN_ID={ADMIN_ID}")

    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас немає доступу до адмін-панелі.")
        return

    await message.answer(
        "🛠 Адмін-панель відкрита.\nОбери дію:",
        reply_markup=admin_menu(),
    )


@admin_router.message(F.text == "👥 Користувачі")
async def show_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text, kb = await _render_users_page(page=1)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("admin_users:page:"))
async def paginate_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Немає доступу.", show_alert=True)
        return

    try:
        page = int(callback.data.rsplit(":", 1)[1])
    except:
        await callback.answer()
        return

    text, kb = await _render_users_page(page=page)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin_users:noop")
async def noop_pagination(callback: types.CallbackQuery):
    await callback.answer()
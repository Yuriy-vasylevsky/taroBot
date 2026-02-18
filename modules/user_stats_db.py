import aiosqlite
from datetime import datetime
from typing import List, Dict, Any, Optional

# DB_PATH = "tarot_users.db"

import os
import shutil

# === PERSISTENT DATABASE ДЛЯ RAILWAY ===
# База завжди буде в volume, щоб не затиралася при деплоях
DB_PATH = "/data/tarot_users.db"

# Автоматичне копіювання старої бази (один раз)
if not os.path.exists(DB_PATH) and os.path.exists("/app/tarot_users.db"):
    try:
        os.makedirs("/data", exist_ok=True)
        shutil.copy2("/app/tarot_users.db", DB_PATH)
        print("✅ Стара база успішно перенесена в persistent volume (/data/tarot_users.db)")
    except Exception as e:
        print(f"⚠️ Не вдалося скопіювати базу: {e}")

# Створюємо папку, якщо чомусь немає
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ======================
#   ІНІЦІАЛІЗАЦІЯ БАЗИ
# ======================
async def init_db():
    """
    Створює таблиці, якщо їх ще немає.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблиця користувачів
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                energy INTEGER DEFAULT 12,
                created_at TEXT DEFAULT (DATETIME('now','localtime')),
                last_active_at TEXT,
                last_card_picked_at TEXT  -- нове поле для зберігання часу витягування карти
            )
            """
        )

        # Таблиця дій користувачів
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                created_at TEXT DEFAULT (DATETIME('now','localtime'))
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,         -- кого запросили
                referrer_id INTEGER,     -- хто запросив
                rewarded INTEGER DEFAULT 0,   -- чи видана нагорода
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.commit()


# ======================
#   ДОПОМОЖНІ
# ======================
async def _upsert_user(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
):
    """
    Створює або оновлює юзера + оновлює last_active_at.
    Час пишемо в локальному форматі (не UTC).
    """
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    username = username or ""
    full_name = full_name or ""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_active_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active_at = excluded.last_active_at
            """,
            (user_id, username, full_name, now),
        )
        await db.commit()

async def _log_action(user_id: int, action: str):
    """
    Логує дію користувача й автоматично залишає тільки останні 5.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 1️⃣ Додаємо нову дію
        await db.execute(
            "INSERT INTO user_actions (user_id, action) VALUES (?, ?)",
            (user_id, action),
        )

        # 2️⃣ Видаляємо зайві — залишаємо лише останні 5
        await db.execute(
            """
            DELETE FROM user_actions
            WHERE id NOT IN (
                SELECT id FROM user_actions
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 5
            )
            AND user_id = ?
            """,
            (user_id, user_id),
        )

        await db.commit()


# ======================
#   ПУБЛІЧНІ ФУНКЦІЇ
# ======================
async def track_user_activity(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    action: str,
):
    """
    Викликаєш у будь-якому хендлері / мідлварі:
    - оновлює/створює юзера
    - пише дію в лог
    """
    await _upsert_user(user_id, username, full_name)
    await _log_action(user_id, action)


async def change_energy(user_id: int, delta: int):
    """
    Додає / віднімає енергію (може бути від'ємною).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # гарантуємо, що юзер є
        await db.execute(
            """
            INSERT INTO users (user_id, energy)
            VALUES (?, 0)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        await db.execute(
            "UPDATE users SET energy = energy + ? WHERE user_id = ?",
            (delta, user_id),
        )
        await db.commit()


async def get_energy(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT energy FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        await cur.close()
    return row[0] if row and row[0] is not None else 0


async def get_users_count() -> int:
    """
    Кількість користувачів (для пагінації).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        await cur.close()
    return int(row[0]) if row and row[0] is not None else 0


async def get_users_with_last_activity_and_actions(
    limit_users: int = 50,
    actions_per_user: int = 5,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Повертає список юзерів з:
    - user_id, username, full_name, energy, last_active_at
    - останні дії (до actions_per_user шт.)
    Відсортовано за останньою активністю (найсвіжіші зверху).
    Підтримує OFFSET для пагінації.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1) Юзери
        cur = await db.execute(
            """
            SELECT user_id, username, full_name, energy, last_active_at
            FROM users
            ORDER BY last_active_at IS NULL, last_active_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit_users, offset),
        )
        users_rows = await cur.fetchall()
        await cur.close()

        if not users_rows:
            return []

        user_ids = [row["user_id"] for row in users_rows]

        # 2) Останні дії по всім одразу
        placeholders = ",".join("?" * len(user_ids))
        cur = await db.execute(
            f"""
            SELECT user_id, action, created_at
            FROM user_actions
            WHERE user_id IN ({placeholders})
            ORDER BY created_at DESC
            """,
            user_ids,
        )
        actions_rows = await cur.fetchall()
        await cur.close()

        # Мапа: user_id -> список останніх дій (тільки текст, без часу)
        actions_map: Dict[int, List[str]] = {uid: [] for uid in user_ids}
        for row in actions_rows:
            uid = row["user_id"]
            if len(actions_map[uid]) < actions_per_user:
                txt = row["action"]  # час окремо не показуємо
                actions_map[uid].append(txt)

        result: List[Dict[str, Any]] = []
        for row in users_rows:
            uid = row["user_id"]
            result.append(
                {
                    "user_id": uid,
                    "username": row["username"],
                    "full_name": row["full_name"],
                    "energy": row["energy"],
                    "last_active_at": row["last_active_at"],
                    "actions": actions_map.get(uid, []),
                }
            )

        return result


# Перевірити чи юзера вже хтось запросив
async def get_referrer(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT referrer_id FROM referrals WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


# Створити запис про реферала
async def add_referral(user_id: int, referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO referrals (user_id, referrer_id)
            VALUES (?, ?)
            """,
            (user_id, referrer_id)
        )
        await db.commit()


# Видати нагороду за реферального юзера
async def reward_referral(referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # шукаємо нероздані реферали
        cur = await db.execute(
            """
            SELECT id FROM referrals
            WHERE referrer_id = ? AND rewarded = 0
            """,
            (referrer_id,)
        )
        row = await cur.fetchone()

        if not row:
            return False  # нема кого винагородити

        ref_id = row[0]

        # видати енергію
        await db.execute(
            "UPDATE users SET energy = energy + 12 WHERE user_id = ?",
            (referrer_id,)
        )

        # відмітити як видану
        await db.execute(
            "UPDATE referrals SET rewarded = 1 WHERE id = ?",
            (ref_id,)
        )

        await db.commit()
        return True

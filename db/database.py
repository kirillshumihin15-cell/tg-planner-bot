import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "planner.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                comment TEXT,
                date TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                billing_day INTEGER NOT NULL,
                comment TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        await db.commit()


# ---------- Tasks ----------

async def add_task(date: str, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tasks (date, text) VALUES (?, ?)", (date, text)
        )
        await db.commit()
        return cur.lastrowid


async def get_tasks(date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE date = ? ORDER BY id", (date,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def toggle_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET done = 1 - done WHERE id = ?", (task_id,)
        )
        await db.commit()


async def delete_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()


# ---------- Transactions ----------

async def add_transaction(type_: str, amount: float, category: str, comment: str, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transactions (type, amount, category, comment, date) VALUES (?, ?, ?, ?, ?)",
            (type_, amount, category, comment, date),
        )
        await db.commit()


async def get_month_summary(year: int, month: int) -> dict:
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT type, category, SUM(amount) as total
               FROM transactions
               WHERE strftime('%Y-%m', date) = ?
               GROUP BY type, category
               ORDER BY type, total DESC""",
            (month_str,),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    return rows


async def get_month_transactions(year: int, month: int) -> list[dict]:
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transactions WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC",
            (month_str,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_transaction(tx_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        await db.commit()


# ---------- Subscriptions ----------

async def add_subscription(name: str, amount: float, billing_day: int, comment: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO subscriptions (name, amount, billing_day, comment) VALUES (?, ?, ?, ?)",
            (name, amount, billing_day, comment),
        )
        await db.commit()


async def get_subscriptions(active_only: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM subscriptions"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY billing_day"
        async with db.execute(query) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_subscription(sub_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        await db.commit()

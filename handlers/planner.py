from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, timedelta

from db.database import add_task, get_tasks, toggle_task, delete_task


class AddTask(StatesGroup):
    waiting_text = State()


def _tasks_keyboard(tasks: list, current_date: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    for t in tasks:
        check = "✅" if t["done"] else "⬜"
        kb.row(
            InlineKeyboardButton(f"{check} {t['text']}", callback_data=f"task:toggle:{t['id']}:{current_date}"),
            InlineKeyboardButton("🗑", callback_data=f"task:del:{t['id']}:{current_date}"),
        )
    kb.add(InlineKeyboardButton("➕ Добавить задачу", callback_data=f"task:add:{current_date}"))

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    nav = []
    if current_date != today:
        nav.append(InlineKeyboardButton("◀ Сегодня", callback_data=f"day:{today}"))
    nav.append(InlineKeyboardButton("Завтра ▶", callback_data=f"day:{tomorrow}"))
    kb.row(*nav)
    kb.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main:menu"))
    return kb


async def show_day(target, day: str, state: FSMContext = None):
    if state:
        await state.finish()
    tasks = await get_tasks(day)
    total = len(tasks)
    done = sum(1 for t in tasks if t["done"])
    d = date.fromisoformat(day)
    label = d.strftime("%-d %B %Y")

    if not tasks:
        text = f"📋 *{label}*\n\nЗадач пока нет. Добавь первую!"
    else:
        text = f"📋 *{label}* — {done}/{total} выполнено\n\n"
        for t in tasks:
            mark = "✅" if t["done"] else "⬜"
            text += f"{mark} {t['text']}\n"

    kb = _tasks_keyboard(tasks, day)
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="Markdown")


def register(dp):
    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("day:"))
    async def on_show_day(call: types.CallbackQuery, state: FSMContext):
        day = call.data.split(":")[1]
        await show_day(call, day, state)

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("task:add:"))
    async def ask_task_text(call: types.CallbackQuery):
        day = call.data.split(":")[2]
        await AddTask.waiting_text.set()
        state = dp.current_state(user=call.from_user.id)
        await state.update_data(day=day)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data=f"day:{day}"))
        await call.message.edit_text("✏️ Введи текст задачи:", reply_markup=kb)
        await call.answer()

    @dp.message_handler(state=AddTask.waiting_text)
    async def save_task(message: types.Message, state: FSMContext):
        data = await state.get_data()
        day = data["day"]
        await add_task(day, message.text.strip())
        await show_day(message, day, state)

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("task:toggle:"))
    async def on_toggle(call: types.CallbackQuery):
        _, _, task_id, day = call.data.split(":")
        await toggle_task(int(task_id))
        await show_day(call, day)

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("task:del:"))
    async def on_delete(call: types.CallbackQuery):
        _, _, task_id, day = call.data.split(":")
        await delete_task(int(task_id))
        await show_day(call, day)


async def send_morning_digest(bot, chat_id: int):
    today = date.today().isoformat()
    tasks = await get_tasks(today)
    d = date.today().strftime("%-d %B")
    if not tasks:
        text = f"☀️ *Доброе утро!*\n\n📋 *{d}*\n\nПлан на сегодня пуст. Открой бота и добавь задачи!"
    else:
        lines = "\n".join(f"⬜ {t['text']}" for t in tasks)
        text = f"☀️ *Доброе утро!*\n\n📋 *{d}* — {len(tasks)} задач\n\n{lines}"
    from handlers.menu import main_menu
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu())

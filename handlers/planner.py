from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta

from db.database import add_task, get_tasks, toggle_task, delete_task

router = Router()


class AddTask(StatesGroup):
    waiting_text = State()


def _tasks_keyboard(tasks: list[dict], current_date: str) -> InlineKeyboardMarkup:
    rows = []
    for t in tasks:
        check = "✅" if t["done"] else "⬜"
        rows.append([
            InlineKeyboardButton(
                text=f"{check} {t['text']}",
                callback_data=f"task:toggle:{t['id']}:{current_date}"
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"task:del:{t['id']}:{current_date}"
            ),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить задачу", callback_data=f"task:add:{current_date}")])

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    nav = []
    if current_date != today:
        nav.append(InlineKeyboardButton(text="◀ Сегодня", callback_data=f"day:{today}"))
    nav.append(InlineKeyboardButton(text="Завтра ▶", callback_data=f"day:{tomorrow}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_day(target: Message | CallbackQuery, day: str, state: FSMContext = None):
    if state:
        await state.clear()
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
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("day:"))
async def show_day(call: CallbackQuery, state: FSMContext):
    day = call.data.split(":")[1]
    await _show_day(call, day, state)


@router.callback_query(F.data.startswith("task:add:"))
async def ask_task_text(call: CallbackQuery, state: FSMContext):
    day = call.data.split(":")[2]
    await state.set_state(AddTask.waiting_text)
    await state.update_data(day=day)
    await call.message.edit_text(
        "✏️ Введи текст задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"day:{day}")]
        ])
    )
    await call.answer()


@router.message(AddTask.waiting_text)
async def save_task(message: Message, state: FSMContext):
    data = await state.get_data()
    day = data["day"]
    await add_task(day, message.text.strip())
    await _show_day(message, day, state)


@router.callback_query(F.data.startswith("task:toggle:"))
async def on_toggle(call: CallbackQuery):
    _, _, task_id, day = call.data.split(":")
    await toggle_task(int(task_id))
    await _show_day(call, day)


@router.callback_query(F.data.startswith("task:del:"))
async def on_delete(call: CallbackQuery):
    _, _, task_id, day = call.data.split(":")
    await delete_task(int(task_id))
    await _show_day(call, day)


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

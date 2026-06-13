from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date

from db.database import add_transaction, get_month_summary, get_month_transactions, delete_transaction

router = Router()

EXPENSE_CATEGORIES = ["🍕 Еда", "🚗 Транспорт", "🏠 Жильё", "🎮 Развлечения", "💊 Здоровье", "📦 Прочее"]
INCOME_CATEGORIES = ["💼 Зарплата", "💸 Фриланс", "🎁 Подарок", "📈 Инвестиции", "📦 Прочее"]


class AddTx(StatesGroup):
    choose_type = State()
    choose_category = State()
    enter_amount = State()
    enter_comment = State()


def _finance_menu_kb() -> InlineKeyboardMarkup:
    today = date.today()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить расход", callback_data="tx:new:expense")],
        [InlineKeyboardButton(text="➕ Добавить доход", callback_data="tx:new:income")],
        [InlineKeyboardButton(text="📊 Сводка за месяц", callback_data=f"tx:summary:{today.year}:{today.month}")],
        [InlineKeyboardButton(text="📜 История", callback_data=f"tx:history:{today.year}:{today.month}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main:menu")],
    ])


def _categories_kb(tx_type: str) -> InlineKeyboardMarkup:
    cats = EXPENSE_CATEGORIES if tx_type == "expense" else INCOME_CATEGORIES
    rows = [[InlineKeyboardButton(text=c, callback_data=f"tx:cat:{tx_type}:{c}")] for c in cats]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="finance:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "finance:menu")
async def finance_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("💰 *Финансы*\n\nВыбери действие:", reply_markup=_finance_menu_kb(), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data.startswith("tx:new:"))
async def choose_category(call: CallbackQuery, state: FSMContext):
    tx_type = call.data.split(":")[2]
    await state.set_state(AddTx.choose_category)
    await state.update_data(tx_type=tx_type)
    label = "расхода" if tx_type == "expense" else "дохода"
    await call.message.edit_text(f"Выбери категорию {label}:", reply_markup=_categories_kb(tx_type))
    await call.answer()


@router.callback_query(F.data.startswith("tx:cat:"))
async def enter_amount(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":", 3)
    tx_type, category = parts[2], parts[3]
    await state.update_data(tx_type=tx_type, category=category)
    await state.set_state(AddTx.enter_amount)
    await call.message.edit_text(
        f"Категория: *{category}*\n\nВведи сумму (например: `1500`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="finance:menu")]
        ])
    )
    await call.answer()


@router.message(AddTx.enter_amount)
async def enter_comment(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи корректную сумму (число больше 0):")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddTx.enter_comment)
    await message.answer(
        "Добавь комментарий или отправь `-` чтобы пропустить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="tx:skip_comment")]
        ])
    )


@router.callback_query(F.data == "tx:skip_comment")
async def skip_comment(call: CallbackQuery, state: FSMContext):
    await _save_transaction(call.message, state, comment="")
    await call.answer()


@router.message(AddTx.enter_comment)
async def save_with_comment(message: Message, state: FSMContext):
    comment = "" if message.text.strip() == "-" else message.text.strip()
    await _save_transaction(message, state, comment=comment)


async def _save_transaction(msg: Message, state: FSMContext, comment: str):
    data = await state.get_data()
    today = date.today().isoformat()
    await add_transaction(data["tx_type"], data["amount"], data["category"], comment, today)
    await state.clear()
    sign = "−" if data["tx_type"] == "expense" else "+"
    await msg.answer(
        f"✅ Записано: *{sign}{data['amount']:.0f} ₽* — {data['category']}",
        parse_mode="Markdown",
        reply_markup=_finance_menu_kb()
    )


@router.callback_query(F.data.startswith("tx:summary:"))
async def show_summary(call: CallbackQuery):
    _, _, year, month = call.data.split(":")
    year, month = int(year), int(month)
    rows = await get_month_summary(year, month)

    income_total = 0.0
    expense_total = 0.0
    income_lines = []
    expense_lines = []

    for r in rows:
        if r["type"] == "income":
            income_total += r["total"]
            income_lines.append(f"  {r['category']}: +{r['total']:.0f} ₽")
        else:
            expense_total += r["total"]
            expense_lines.append(f"  {r['category']}: −{r['total']:.0f} ₽")

    month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    text = f"📊 *{month_names[month]} {year}*\n\n"

    if income_lines:
        text += f"💚 *Доходы: +{income_total:.0f} ₽*\n" + "\n".join(income_lines) + "\n\n"
    else:
        text += "💚 Доходов нет\n\n"

    if expense_lines:
        text += f"❤️ *Расходы: −{expense_total:.0f} ₽*\n" + "\n".join(expense_lines) + "\n\n"
    else:
        text += "❤️ Расходов нет\n\n"

    balance = income_total - expense_total
    sign = "+" if balance >= 0 else ""
    text += f"💼 *Баланс: {sign}{balance:.0f} ₽*"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data="finance:menu")]
    ]))
    await call.answer()


@router.callback_query(F.data.startswith("tx:history:"))
async def show_history(call: CallbackQuery):
    _, _, year, month = call.data.split(":")
    txs = await get_month_transactions(int(year), int(month))

    if not txs:
        text = "История пуста."
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="finance:menu")]])
    else:
        lines = []
        for t in txs[:20]:
            sign = "−" if t["type"] == "expense" else "+"
            comment = f" ({t['comment']})" if t["comment"] else ""
            lines.append(f"{t['date'][5:]} {sign}{t['amount']:.0f}₽ {t['category']}{comment}")
        text = "📜 *История (последние 20)*\n\n" + "\n".join(lines)
        rows = [[InlineKeyboardButton(text=f"🗑 Удалить запись #{t['id']}", callback_data=f"tx:del:{t['id']}")] for t in txs[:10]]
        rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="finance:menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("tx:del:"))
async def delete_tx(call: CallbackQuery):
    tx_id = int(call.data.split(":")[2])
    await delete_transaction(tx_id)
    await call.answer("Удалено ✅")
    today = date.today()
    call.data = f"tx:history:{today.year}:{today.month}"
    await show_history(call)

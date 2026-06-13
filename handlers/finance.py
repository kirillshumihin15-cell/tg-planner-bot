from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date

from db.database import add_transaction, get_month_summary, get_month_transactions, delete_transaction

EXPENSE_CATEGORIES = ["🍕 Еда", "🚗 Транспорт", "🏠 Жильё", "🎮 Развлечения", "💊 Здоровье", "📦 Прочее"]
INCOME_CATEGORIES = ["💼 Зарплата", "💸 Фриланс", "🎁 Подарок", "📈 Инвестиции", "📦 Прочее"]


class AddTx(StatesGroup):
    choose_category = State()
    enter_amount = State()
    enter_comment = State()


def _finance_menu_kb() -> InlineKeyboardMarkup:
    today = date.today()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Добавить расход", callback_data="tx:new:expense"),
        InlineKeyboardButton("➕ Добавить доход", callback_data="tx:new:income"),
        InlineKeyboardButton("📊 Сводка за месяц", callback_data=f"tx:summary:{today.year}:{today.month}"),
        InlineKeyboardButton("📜 История", callback_data=f"tx:history:{today.year}:{today.month}"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main:menu"),
    )
    return kb


def _categories_kb(tx_type: str) -> InlineKeyboardMarkup:
    cats = EXPENSE_CATEGORIES if tx_type == "expense" else INCOME_CATEGORIES
    kb = InlineKeyboardMarkup(row_width=1)
    for c in cats:
        kb.add(InlineKeyboardButton(c, callback_data=f"tx:cat:{tx_type}:{c}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="finance:menu"))
    return kb


def register(dp):
    @dp.callback_query_handler(lambda c: c.data == "finance:menu", state="*")
    async def finance_menu(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await call.message.edit_text("💰 *Финансы*\n\nВыбери действие:", reply_markup=_finance_menu_kb(), parse_mode="Markdown")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("tx:new:"))
    async def choose_category(call: types.CallbackQuery, state: FSMContext):
        tx_type = call.data.split(":")[2]
        await AddTx.choose_category.set()
        await state.update_data(tx_type=tx_type)
        label = "расхода" if tx_type == "expense" else "дохода"
        await call.message.edit_text(f"Выбери категорию {label}:", reply_markup=_categories_kb(tx_type))
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("tx:cat:"), state=AddTx.choose_category)
    async def enter_amount(call: types.CallbackQuery, state: FSMContext):
        parts = call.data.split(":", 3)
        tx_type, category = parts[2], parts[3]
        await state.update_data(tx_type=tx_type, category=category)
        await AddTx.enter_amount.set()
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="finance:menu"))
        await call.message.edit_text(
            f"Категория: *{category}*\n\nВведи сумму (например: `1500`):",
            parse_mode="Markdown", reply_markup=kb
        )
        await call.answer()

    @dp.message_handler(state=AddTx.enter_amount)
    async def ask_comment(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", ".")
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Введи корректную сумму (число больше 0):")
            return
        await state.update_data(amount=amount)
        await AddTx.enter_comment.set()
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="tx:skip_comment"))
        await message.answer("Добавь комментарий или нажми Пропустить:", reply_markup=kb)

    @dp.callback_query_handler(lambda c: c.data == "tx:skip_comment", state=AddTx.enter_comment)
    async def skip_comment(call: types.CallbackQuery, state: FSMContext):
        await _save_transaction(call.message, state, comment="")
        await call.answer()

    @dp.message_handler(state=AddTx.enter_comment)
    async def save_comment(message: types.Message, state: FSMContext):
        comment = "" if message.text.strip() == "-" else message.text.strip()
        await _save_transaction(message, state, comment=comment)

    async def _save_transaction(msg: types.Message, state: FSMContext, comment: str):
        data = await state.get_data()
        today = date.today().isoformat()
        await add_transaction(data["tx_type"], data["amount"], data["category"], comment, today)
        await state.finish()
        sign = "−" if data["tx_type"] == "expense" else "+"
        await msg.answer(
            f"✅ Записано: *{sign}{data['amount']:.0f} ₽* — {data['category']}",
            parse_mode="Markdown", reply_markup=_finance_menu_kb()
        )

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("tx:summary:"))
    async def show_summary(call: types.CallbackQuery):
        _, _, year, month = call.data.split(":")
        year, month = int(year), int(month)
        rows = await get_month_summary(year, month)

        income_total = expense_total = 0.0
        income_lines, expense_lines = [], []
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
        text += (f"💚 *Доходы: +{income_total:.0f} ₽*\n" + "\n".join(income_lines) + "\n\n") if income_lines else "💚 Доходов нет\n\n"
        text += (f"❤️ *Расходы: −{expense_total:.0f} ₽*\n" + "\n".join(expense_lines) + "\n\n") if expense_lines else "❤️ Расходов нет\n\n"
        balance = income_total - expense_total
        text += f"💼 *Баланс: {'+' if balance >= 0 else ''}{balance:.0f} ₽*"

        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀ Назад", callback_data="finance:menu"))
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("tx:history:"))
    async def show_history(call: types.CallbackQuery):
        _, _, year, month = call.data.split(":")
        txs = await get_month_transactions(int(year), int(month))
        if not txs:
            text = "История пуста."
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀ Назад", callback_data="finance:menu"))
        else:
            lines = []
            for t in txs[:20]:
                sign = "−" if t["type"] == "expense" else "+"
                comment = f" ({t['comment']})" if t["comment"] else ""
                lines.append(f"{t['date'][5:]} {sign}{t['amount']:.0f}₽ {t['category']}{comment}")
            text = "📜 *История (последние 20)*\n\n" + "\n".join(lines)
            kb = InlineKeyboardMarkup(row_width=1)
            for t in txs[:10]:
                kb.add(InlineKeyboardButton(f"🗑 #{t['id']} {t['amount']:.0f}₽", callback_data=f"tx:del:{t['id']}"))
            kb.add(InlineKeyboardButton("◀ Назад", callback_data="finance:menu"))
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("tx:del:"))
    async def delete_tx(call: types.CallbackQuery):
        tx_id = int(call.data.split(":")[2])
        await delete_transaction(tx_id)
        await call.answer("Удалено ✅")
        today = date.today()
        call.data = f"tx:history:{today.year}:{today.month}"
        txs = await get_month_transactions(today.year, today.month)
        if not txs:
            text = "История пуста."
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀ Назад", callback_data="finance:menu"))
        else:
            lines = []
            for t in txs[:20]:
                sign = "−" if t["type"] == "expense" else "+"
                comment = f" ({t['comment']})" if t["comment"] else ""
                lines.append(f"{t['date'][5:]} {sign}{t['amount']:.0f}₽ {t['category']}{comment}")
            text = "📜 *История (последние 20)*\n\n" + "\n".join(lines)
            kb = InlineKeyboardMarkup(row_width=1)
            for t in txs[:10]:
                kb.add(InlineKeyboardButton(f"🗑 #{t['id']} {t['amount']:.0f}₽", callback_data=f"tx:del:{t['id']}"))
            kb.add(InlineKeyboardButton("◀ Назад", callback_data="finance:menu"))
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

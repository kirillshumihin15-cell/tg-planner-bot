from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date

from db.database import add_subscription, get_subscriptions, delete_subscription

router = Router()


class AddSub(StatesGroup):
    name = State()
    amount = State()
    billing_day = State()
    comment = State()


def _subs_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить подписку", callback_data="subs:add")],
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="subs:list")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main:menu")],
    ])


@router.callback_query(F.data == "subs:menu")
async def subs_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🔔 *Подписки*\n\nВыбери действие:", reply_markup=_subs_menu_kb(), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "subs:add")
async def ask_name(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddSub.name)
    await call.message.edit_text(
        "Введи название подписки (например: *Netflix*):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="subs:menu")]
        ])
    )
    await call.answer()


@router.message(AddSub.name)
async def ask_amount(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddSub.amount)
    await message.answer("Введи сумму списания (₽):")


@router.message(AddSub.amount)
async def ask_billing_day(message: Message, state: FSMContext):
    text = message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи корректную сумму:")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddSub.billing_day)
    await message.answer("В какой день месяца списывается? (1–31):")


@router.message(AddSub.billing_day)
async def ask_comment(message: Message, state: FSMContext):
    try:
        day = int(message.text.strip())
        if not 1 <= day <= 31:
            raise ValueError
    except ValueError:
        await message.answer("Введи число от 1 до 31:")
        return
    await state.update_data(billing_day=day)
    await state.set_state(AddSub.comment)
    await message.answer(
        "Добавь комментарий или отправь `-` чтобы пропустить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="subs:skip_comment")]
        ])
    )


@router.callback_query(F.data == "subs:skip_comment")
async def skip_sub_comment(call: CallbackQuery, state: FSMContext):
    await _save_subscription(call.message, state, comment="")
    await call.answer()


@router.message(AddSub.comment)
async def save_sub_comment(message: Message, state: FSMContext):
    comment = "" if message.text.strip() == "-" else message.text.strip()
    await _save_subscription(message, state, comment=comment)


async def _save_subscription(msg: Message, state: FSMContext, comment: str):
    data = await state.get_data()
    await add_subscription(data["name"], data["amount"], data["billing_day"], comment)
    await state.clear()
    await msg.answer(
        f"✅ Подписка *{data['name']}* добавлена!\n"
        f"Сумма: {data['amount']:.0f} ₽ каждого {data['billing_day']}-го числа",
        parse_mode="Markdown",
        reply_markup=_subs_menu_kb()
    )


@router.callback_query(F.data == "subs:list")
async def list_subs(call: CallbackQuery):
    subs = await get_subscriptions()
    if not subs:
        text = "У тебя нет активных подписок."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="subs:add")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="subs:menu")],
        ])
    else:
        today_day = date.today().day
        lines = []
        total = 0.0
        for s in subs:
            days_left = s["billing_day"] - today_day
            if days_left < 0:
                days_left += 31
            flag = "⚠️" if days_left <= 3 else "🔔"
            comment = f" — {s['comment']}" if s["comment"] else ""
            lines.append(f"{flag} *{s['name']}* {s['amount']:.0f}₽/мес (списание {s['billing_day']}-го){comment}")
            total += s["amount"]

        text = "🔔 *Мои подписки*\n\n" + "\n".join(lines) + f"\n\n💼 Итого в месяц: *{total:.0f} ₽*"
        rows = [[InlineKeyboardButton(text=f"🗑 {s['name']}", callback_data=f"subs:del:{s['id']}")] for s in subs]
        rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="subs:menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("subs:del:"))
async def delete_sub(call: CallbackQuery):
    sub_id = int(call.data.split(":")[2])
    await delete_subscription(sub_id)
    await call.answer("Подписка удалена ✅")
    call.data = "subs:list"
    await list_subs(call)


async def send_subscription_alerts(bot, chat_id: int):
    subs = await get_subscriptions()
    today_day = date.today().day
    alerts = [s for s in subs if 0 <= s["billing_day"] - today_day <= 3]
    if not alerts:
        return
    lines = [f"⚠️ *{s['name']}* — {s['amount']:.0f} ₽ списывается {s['billing_day']}-го" for s in alerts]
    text = "🔔 *Напоминание о подписках:*\n\n" + "\n".join(lines)
    await bot.send_message(chat_id, text, parse_mode="Markdown")

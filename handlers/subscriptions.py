from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date

from db.database import add_subscription, get_subscriptions, delete_subscription


class AddSub(StatesGroup):
    name = State()
    amount = State()
    billing_day = State()
    comment = State()


def _subs_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Добавить подписку", callback_data="subs:add"),
        InlineKeyboardButton("📋 Мои подписки", callback_data="subs:list"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main:menu"),
    )
    return kb


def register(dp):
    @dp.callback_query_handler(lambda c: c.data == "subs:menu", state="*")
    async def subs_menu(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await call.message.edit_text("🔔 *Подписки*\n\nВыбери действие:", reply_markup=_subs_menu_kb(), parse_mode="Markdown")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "subs:add")
    async def ask_name(call: types.CallbackQuery):
        await AddSub.name.set()
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="subs:menu"))
        await call.message.edit_text("Введи название подписки (например: *Netflix*):", parse_mode="Markdown", reply_markup=kb)
        await call.answer()

    @dp.message_handler(state=AddSub.name)
    async def ask_amount(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await AddSub.amount.set()
        await message.answer("Введи сумму списания (₽):")

    @dp.message_handler(state=AddSub.amount)
    async def ask_billing_day(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", ".")
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Введи корректную сумму:")
            return
        await state.update_data(amount=amount)
        await AddSub.billing_day.set()
        await message.answer("В какой день месяца списывается? (1–31):")

    @dp.message_handler(state=AddSub.billing_day)
    async def ask_comment(message: types.Message, state: FSMContext):
        try:
            day = int(message.text.strip())
            if not 1 <= day <= 31:
                raise ValueError
        except ValueError:
            await message.answer("Введи число от 1 до 31:")
            return
        await state.update_data(billing_day=day)
        await AddSub.comment.set()
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="subs:skip_comment"))
        await message.answer("Добавь комментарий или нажми Пропустить:", reply_markup=kb)

    @dp.callback_query_handler(lambda c: c.data == "subs:skip_comment", state=AddSub.comment)
    async def skip_comment(call: types.CallbackQuery, state: FSMContext):
        await _save_subscription(call.message, state, comment="")
        await call.answer()

    @dp.message_handler(state=AddSub.comment)
    async def save_comment(message: types.Message, state: FSMContext):
        comment = "" if message.text.strip() == "-" else message.text.strip()
        await _save_subscription(message, state, comment=comment)

    async def _save_subscription(msg: types.Message, state: FSMContext, comment: str):
        data = await state.get_data()
        await add_subscription(data["name"], data["amount"], data["billing_day"], comment)
        await state.finish()
        await msg.answer(
            f"✅ Подписка *{data['name']}* добавлена!\n"
            f"Сумма: {data['amount']:.0f} ₽ каждого {data['billing_day']}-го числа",
            parse_mode="Markdown", reply_markup=_subs_menu_kb()
        )

    @dp.callback_query_handler(lambda c: c.data == "subs:list")
    async def list_subs(call: types.CallbackQuery):
        subs = await get_subscriptions()
        if not subs:
            text = "У тебя нет активных подписок."
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(
                InlineKeyboardButton("➕ Добавить", callback_data="subs:add"),
                InlineKeyboardButton("◀ Назад", callback_data="subs:menu"),
            )
        else:
            today_day = date.today().day
            lines, total = [], 0.0
            for s in subs:
                days_left = s["billing_day"] - today_day
                if days_left < 0:
                    days_left += 31
                flag = "⚠️" if days_left <= 3 else "🔔"
                comment = f" — {s['comment']}" if s["comment"] else ""
                lines.append(f"{flag} *{s['name']}* {s['amount']:.0f}₽/мес (списание {s['billing_day']}-го){comment}")
                total += s["amount"]
            text = "🔔 *Мои подписки*\n\n" + "\n".join(lines) + f"\n\n💼 Итого в месяц: *{total:.0f} ₽*"
            kb = InlineKeyboardMarkup(row_width=1)
            for s in subs:
                kb.add(InlineKeyboardButton(f"🗑 {s['name']}", callback_data=f"subs:del:{s['id']}"))
            kb.add(InlineKeyboardButton("◀ Назад", callback_data="subs:menu"))
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("subs:del:"))
    async def delete_sub(call: types.CallbackQuery):
        sub_id = int(call.data.split(":")[2])
        await delete_subscription(sub_id)
        await call.answer("Подписка удалена ✅")
        subs = await get_subscriptions()
        if not subs:
            text = "У тебя нет активных подписок."
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(
                InlineKeyboardButton("➕ Добавить", callback_data="subs:add"),
                InlineKeyboardButton("◀ Назад", callback_data="subs:menu"),
            )
        else:
            today_day = date.today().day
            lines, total = [], 0.0
            for s in subs:
                days_left = s["billing_day"] - today_day
                if days_left < 0:
                    days_left += 31
                flag = "⚠️" if days_left <= 3 else "🔔"
                comment = f" — {s['comment']}" if s["comment"] else ""
                lines.append(f"{flag} *{s['name']}* {s['amount']:.0f}₽/мес (списание {s['billing_day']}-го){comment}")
                total += s["amount"]
            text = "🔔 *Мои подписки*\n\n" + "\n".join(lines) + f"\n\n💼 Итого в месяц: *{total:.0f} ₽*"
            kb = InlineKeyboardMarkup(row_width=1)
            for s in subs:
                kb.add(InlineKeyboardButton(f"🗑 {s['name']}", callback_data=f"subs:del:{s['id']}"))
            kb.add(InlineKeyboardButton("◀ Назад", callback_data="subs:menu"))
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


async def send_subscription_alerts(bot, chat_id: int):
    subs = await get_subscriptions()
    today_day = date.today().day
    alerts = [s for s in subs if 0 <= s["billing_day"] - today_day <= 3]
    if not alerts:
        return
    lines = [f"⚠️ *{s['name']}* — {s['amount']:.0f} ₽ списывается {s['billing_day']}-го" for s in alerts]
    await bot.send_message(chat_id, "🔔 *Напоминание о подписках:*\n\n" + "\n".join(lines), parse_mode="Markdown")

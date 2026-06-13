from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date


def main_menu() -> InlineKeyboardMarkup:
    today = date.today().isoformat()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📋 План на сегодня", callback_data=f"day:{today}"),
        InlineKeyboardButton("💰 Финансы", callback_data="finance:menu"),
        InlineKeyboardButton("🔔 Подписки", callback_data="subs:menu"),
    )
    return kb

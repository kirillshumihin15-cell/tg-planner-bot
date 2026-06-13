from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date


def main_menu() -> InlineKeyboardMarkup:
    today = date.today().isoformat()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 План на сегодня", callback_data=f"day:{today}")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance:menu")],
        [InlineKeyboardButton(text="🔔 Подписки", callback_data="subs:menu")],
    ])

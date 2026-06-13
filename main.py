import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from db.database import init_db
from handlers.menu import main_menu
from handlers import planner, finance, subscriptions
from handlers.planner import send_morning_digest
from handlers.subscriptions import send_subscription_alerts

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
MSK = pytz.timezone("Europe/Moscow")


async def on_start(message: Message):
    await message.answer(
        "👋 Привет! Я твой личный планировщик.\n\nВыбери раздел:",
        reply_markup=main_menu()
    )


async def on_main_menu(call: CallbackQuery):
    await call.message.edit_text("Выбери раздел:", reply_markup=main_menu())
    await call.answer()


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(on_start, F.text == "/start")
    dp.callback_query.register(on_main_menu, F.data == "main:menu")
    dp.include_router(planner.router)
    dp.include_router(finance.router)
    dp.include_router(subscriptions.router)

    scheduler = AsyncIOScheduler(timezone=MSK)
    scheduler.add_job(
        send_morning_digest,
        CronTrigger(hour=8, minute=0, timezone=MSK),
        args=[bot, CHAT_ID],
    )
    scheduler.add_job(
        send_subscription_alerts,
        CronTrigger(hour=8, minute=5, timezone=MSK),
        args=[bot, CHAT_ID],
    )
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

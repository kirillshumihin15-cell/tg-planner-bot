import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
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


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)

    @dp.message_handler(commands=["start"])
    async def on_start(message: types.Message):
        await message.answer("👋 Привет! Я твой личный планировщик.\n\nВыбери раздел:", reply_markup=main_menu())

    @dp.callback_query_handler(lambda c: c.data == "main:menu", state="*")
    async def on_main_menu(call: types.CallbackQuery):
        await call.message.edit_text("Выбери раздел:", reply_markup=main_menu())
        await call.answer()

    planner.register(dp)
    finance.register(dp)
    subscriptions.register(dp)

    scheduler = AsyncIOScheduler(timezone=MSK)
    scheduler.add_job(send_morning_digest, CronTrigger(hour=8, minute=0, timezone=MSK), args=[bot, CHAT_ID])
    scheduler.add_job(send_subscription_alerts, CronTrigger(hour=8, minute=5, timezone=MSK), args=[bot, CHAT_ID])
    scheduler.start()

    await dp.start_polling()


if __name__ == "__main__":
    asyncio.run(main())

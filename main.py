# main.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.game_handlers import router as game_router

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        print("Ошибка: не найден TELEGRAM_TOKEN")
        return

    bot = Bot(token=telegram_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(game_router)

    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")

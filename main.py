import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from dotenv import load_dotenv

# Импортируем наши роутеры
from handlers import game_handlers, admin_handlers

async def main():
    load_dotenv()
    bot = Bot(token=getenv("BOT_TOKEN"), parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(admin_handlers.router)
    dp.include_router(game_handlers.router)
    
    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

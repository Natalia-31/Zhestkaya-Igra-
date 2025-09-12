# main.py

import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode

from handlers import game_handlers
from handlers import admin_handlers # <--- 1. ДОБАВЬТЕ ЭТУ СТРОКУ

# ... (остальной код main.py) ...

async def main():
    bot = Bot(token=getenv("BOT_TOKEN"), parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    dp.include_router(game_handlers.router)
    dp.include_router(admin_handlers.router) # <--- 2. И ЭТУ СТРОКУ

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


# main.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
# Добавляем новый импорт для правильной инициализации
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Импортируем наши обработчики
from handlers import game_handlers, admin_handlers

async def main():
    # Загружаем переменные окружения из .env файла
    load_dotenv()
    
    # Правильная инициализация бота для новых версий aiogram
    bot = Bot(
        token=getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера
    dp = Dispatcher()

    # Подключаем роутеры с командами
    dp.include_router(admin_handlers.router)
    dp.include_router(game_handlers.router)
    
    # Удаляем вебхук и запускаем long polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Настраиваем логирование для отладки
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


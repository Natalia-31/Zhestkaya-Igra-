import os
import inspect
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import openai

import game_utils
from config import OPENAI_API_KEY, OPENAI_SETTINGS
from handlers.game_handlers import router as game_router

# Логирование
logging.basicConfig(level=logging.INFO)


async def main():
    # Загрузка .env и проверка ключей
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан в переменных окружения")

    # Инициализация OpenAI
    openai.api_key = OPENAI_API_KEY

    # Отладочная информация
    print("CWD:", os.getcwd())
    print("game_utils file:", inspect.getfile(game_utils))

    # Инициализация бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(game_router)

    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

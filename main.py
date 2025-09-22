import os
import asyncio
import inspect
import pathlib
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import openai

from handlers.game_handlers import router as game_router
import game_utils

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

async def main():
    # Загрузка переменных окружения
    load_dotenv()

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан в .env")

    # Инициализация OpenAI
    openai.api_key = OPENAI_API_KEY

    # Отладочная информация
    print("CWD:", os.getcwd())
    print("game_utils file:", inspect.getfile(game_utils))
    print("situations path:", pathlib.Path(game_utils.decks.sit_path))
    print("answers path:", pathlib.Path(game_utils.decks.ans_path))
    print("situations loaded:", len(game_utils.decks.situations))
    print("answers loaded:", len(game_utils.decks.answers))

    # Инициализация бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Подключение роутеров
    dp.include_router(game_router)

    # Запуск
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

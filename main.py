import os
import inspect
import pathlib
import game_utils
print("CWD:", os.getcwd())
print("game_utils file:", inspect.getfile(game_utils))
print("situations path:", pathlib.Path(game_utils.decks.sit_path))
print("answers path:", pathlib.Path(game_utils.decks.ans_path))
print("situations loaded:", len(game_utils.decks.situations))
print("answers loaded:", len(game_utils.decks.answers))

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from handlers.game_handlers import router as game_router

# Импорт функции генерации OpenAI картинки
from image_generator import generate_image_openai

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(game_router)

    # ======= ПРИМЕР: Генерация картинки через OpenAI (переносите этот вызов в ваши хэндлеры!) =======
    # situation = "Игрок встречает мудрого старца"
    # answer = "Получает секретный предмет"
    # image_url = generate_image_openai(situation, answer)
    # print("OpenAI image URL:", image_url)
    # ================================================================================================

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

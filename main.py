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
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from handlers.game_handlers import router as game_router

import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Путь к приветственному видео
WELCOME_VIDEO_PATH = "assets/welcome.mp4"  # Измените на свой путь к видео

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def generate_gemini_response(text: str) -> str:
    model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
    response = model.generate_content(text)
    return response.text

async def send_welcome_video(message: Message, bot: Bot):
    """Отправляет приветственное видео при старте"""
    try:
        if os.path.exists(WELCOME_VIDEO_PATH):
            video = FSInputFile(WELCOME_VIDEO_PATH)
            await bot.send_video(
                chat_id=message.chat.id,
                video=video,
                caption="🎮 Добро пожаловать в игру! Приятной игры!"
            )
        else:
            await message.answer("🎮 Добро пожаловать в игру!")
            logging.warning(f"Видео не найдено по пути: {WELCOME_VIDEO_PATH}")
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного видео: {e}")
        await message.answer("🎮 Добро пожаловать в игру!")

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY не задан в переменных окружения")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем обработчик команды /start для приветственного видео
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        await send_welcome_video(message, bot)
    
    dp.include_router(game_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

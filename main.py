import os
import inspect
import pathlib
import game_utils
import random
import asyncio

print("CWD:", os.getcwd())
print("game_utils file:", inspect.getfile(game_utils))
print("situations path:", pathlib.Path(game_utils.decks.sit_path))
print("answers path:", pathlib.Path(game_utils.decks.ans_path))
print("situations loaded:", len(game_utils.decks.situations))
print("answers loaded:", len(game_utils.decks.answers))

import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from handlers.game_handlers import router as game_router

import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Путь к приветственному видео
WELCOME_VIDEO_PATH = "assets/welcome.mp4"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ==================== КЛАСС БОТА-ИГРОКА ====================
class BotPlayer:
    """Класс бота-игрока, который автоматически играет в игру"""
    
    def __init__(self, name: str, bot_id: int):
        self.name = name
        self.bot_id = bot_id
        self.use_ai = True  # Использовать ли AI для ответов
        
    async def generate_answer(self, situation: str, available_answers: list) -> str:
        """Генерирует ответ на ситуацию"""
        if self.use_ai and GEMINI_API_KEY:
            try:
                # Используем Gemini для умного выбора ответа
                prompt = f"""Ты играешь в игру. Тебе дана ситуация и список возможных ответов.
Выбери ТОЛЬКО ОДИН самый подходящий и смешной ответ из списка.
Верни только текст выбранного ответа, без дополнительных пояснений.

Ситуация: {situation}

Доступные ответы:
{chr(10).join([f"- {ans}" for ans in available_answers])}

Твой выбор:"""
                
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = await asyncio.to_thread(model.generate_content, prompt)
                answer = response.text.strip()
                
                # Проверяем, что ответ есть в списке доступных
                for available in available_answers:
                    if available.lower() in answer.lower() or answer.lower() in available.lower():
                        return available
                
                # Если AI не выбрал из списка, выбираем случайно
                return random.choice(available_answers)
                
            except Exception as e:
                logging.error(f"Ошибка при генерации ответа ботом {self.name}: {e}")
                return random.choice(available_answers)
        else:
            # Простой случайный выбор, если AI недоступен
            return random.choice(available_answers)
    
    async def play_turn(self, situation: str, available_answers: list) -> str:
        """Делает ход в игре"""
        # Небольшая задержка для имитации "размышлений"
        await asyncio.sleep(random.uniform(1.5, 3.5))
        answer = await self.generate_answer(situation, available_answers)
        logging.info(f"Бот {self.name} выбрал ответ: {answer}")
        return answer


# Создаем двух ботов-игроков
bot_player_1 = BotPlayer("🤖 БотИгрок1", bot_id=1)
bot_player_2 = BotPlayer("🤖 БотИгрок2", bot_id=2)
# ============================================================


async def generate_gemini_response(text: str) -> str:
    """Генерирует ответ с помощью Gemini AI"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
        response = await asyncio.to_thread(model.generate_content, text)
        return response.text
    except Exception as e:
        logging.error(f"Ошибка генерации ответа Gemini: {e}")
        return "Извините, произошла ошибка при генерации ответа."


async def send_welcome_video(message: Message, bot: Bot):
    """Отправляет приветственное видео при старте"""
    try:
        if os.path.exists(WELCOME_VIDEO_PATH):
            video = FSInputFile(WELCOME_VIDEO_PATH)
            await bot.send_video(
                chat_id=message.chat.id,
                video=video,
                caption="🎮 Добро пожаловать в игру! Приятной игры!\n\n"
                        "В игре с вами будут играть два бота: 🤖 БотИгрок1 и 🤖 БотИгрок2"
            )
        else:
            await message.answer(
                "🎮 Добро пожаловать в игру!\n\n"
                "В игре с вами будут играть два бота: 🤖 БотИгрок1 и 🤖 БотИгрок2"
            )
            logging.warning(f"Видео не найдено по пути: {WELCOME_VIDEO_PATH}")
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного видео: {e}")
        await message.answer(
            "🎮 Добро пожаловать в игру!\n\n"
            "В игре с вами будут играть два бота: 🤖 БотИгрок1 и 🤖 БотИгрок2"
        )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY не задан в переменных окружения")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Делаем ботов-игроков доступными для всех обработчиков
    dp.workflow_data.update(bot_players=[bot_player_1, bot_player_2])
    
    # Регистрируем обработчик команды /start для приветственного видео
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        await send_welcome_video(message, bot)
    
    dp.include_router(game_router)
    
    logging.info("Бот запущен и готов к работе")
    logging.info("Боты-игроки активированы: 🤖 БотИгрок1 и 🤖 БотИгрок2")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

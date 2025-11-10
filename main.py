import os
import inspect
import pathlib
import game_utils
import random
import asyncio
import re

print("CWD:", os.getcwd())
print("game_utils file:", inspect.getfile(game_utils))
print("situations path:", pathlib.Path(game_utils.decks.sit_path))
print("answers path:", pathlib.Path(game_utils.decks.ans_path))
print("situations loaded:", len(game_utils.decks.situations))
print("answers loaded:", len(game_utils.decks.answers))

import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from handlers.game_handlers import router as game_router, set_bot_players

import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
    
    async def choose_winner(self, situation: str, players_answers: list) -> int:
        """
        Выбирает лучший ответ как ведущий
        
        Args:
            situation: Игровая ситуация
            players_answers: Список кортежей (имя_игрока, ответ)
        
        Returns:
            Индекс победителя (0, 1, 2, ...)
        """
        if self.use_ai and GEMINI_API_KEY:
            try:
                # Формируем список ответов для AI
                answers_text = "\n".join([
                    f"{i+1}. {name}: {answer}" 
                    for i, (name, answer) in enumerate(players_answers)
                ])
                
                prompt = f"""Ты ведущий в игре. Твоя задача - выбрать самый смешной, остроумный и подходящий ответ.

Ситуация: {situation}

Ответы игроков:
{answers_text}

Выбери ТОЛЬКО НОМЕР лучшего ответа (1, 2, 3 и т.д.).
Верни только число, без пояснений."""
                
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = await asyncio.to_thread(model.generate_content, prompt)
                answer_text = response.text.strip()
                
                # Извлекаем номер из ответа
                numbers = re.findall(r'\d+', answer_text)
                if numbers:
                    chosen_number = int(numbers[0])
                    # Конвертируем в индекс (от 1 до 0-based)
                    if 1 <= chosen_number <= len(players_answers):
                        chosen_idx = chosen_number - 1
                        print(f"🤖 Бот-ведущий {self.name} выбрал ответ #{chosen_number}: {players_answers[chosen_idx][1]}")
                        return chosen_idx
                
                # Если AI не дал корректный ответ
                print(f"⚠️ AI вернул некорректный номер: {answer_text}")
                return random.randint(0, len(players_answers) - 1)
                
            except Exception as e:
                logging.error(f"Ошибка при выборе победителя ботом {self.name}: {e}")
                return random.randint(0, len(players_answers) - 1)
        else:
            # Случайный выбор если AI недоступен
            return random.randint(0, len(players_answers) - 1)


# Создаем двух ботов-игроков
bot_player_1 = BotPlayer("🤖 БотИгрок1", bot_id=1)
bot_player_2 = BotPlayer("🤖 БотИгрок2", bot_id=2)

# Регистрируем ботов в handlers
set_bot_players([bot_player_1, bot_player_2])
# ============================================================


async def generate_gemini_response(text: str) -> str:
    """Генерирует ответ с помощью Gemini AI"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await asyncio.to_thread(model.generate_content, text)
        return response.text
    except Exception as e:
        logging.error(f"Ошибка генерации ответа Gemini: {e}")
        return "Извините, произошла ошибка при генерации ответа."


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY не задан в переменных окружения")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаем роутер с игровыми обработчиками
    dp.include_router(game_router)
    
    logging.info("Бот запущен и готов к работе")
    logging.info("Боты-игроки активированы: 🤖 БотИгрок1 и 🤖 БотИгрок2")
    logging.info("Боты могут быть ведущими и автоматически выбирать победителей")
    logging.info("Ответы игроков отображаются анонимно")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

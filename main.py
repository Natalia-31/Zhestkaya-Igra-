"""
Telegram-бот "Жесткая Игра" - аналог Cards Against Humanity
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import BOT_TOKEN, ADMIN_IDS
import game_handlers
from admin_handlers import register_admin_handlers
from database.models import init_db

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def set_bot_commands(bot: Bot):
    """Устанавливает команды бота"""
    commands = [
        BotCommand(command="start", description="🎮 Начать игру"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="new_game", description="🆕 Создать новую игру"),
        BotCommand(command="join", description="➕ Присоединиться к игре"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="settings", description="⚙️ Настройки игры"),
    ]
    await bot.set_my_commands(commands)

async def main():
    """Главная функция запуска бота"""
    # Инициализация базы данных
    await init_db()

    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация хендлеров
    register_game_handlers(dp)
    register_admin_handlers(dp)

    # Установка команд
    await set_bot_commands(bot)

    logger.info("🤖 Бот 'Жесткая Игра' запущен!")

    try:
        # Запуск polling
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

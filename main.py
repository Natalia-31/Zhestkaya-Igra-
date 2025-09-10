import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем хендлеры из вашего файла
from handlers import game_handlers

async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Получаем токен из переменных окружения
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        print("Ошибка: не найден TELEGRAM_TOKEN в переменных окружения.")
        return

    # Объекты бота и диспетчера
    bot = Bot(token=telegram_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем роутеры
    dp.include_router(game_handlers.router)
    
    print("Бот запущен...")
    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")

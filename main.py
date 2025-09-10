import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers import router  # Импорт вашего роутера

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def main():
    # Получаем токен бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Инициализация бота
    bot = Bot(
        token=bot_token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Диспетчер
    dp = Dispatcher()
    
    # Подключаем роутеры
    dp.include_router(router)
    
    print("🚀 Бот запускается...")
    
    try:
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers import router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Отключаем некоторые назойливые логи
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.session").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def main():
    """Главная функция запуска бота."""
    print("🚀 Запуск Жесткой Игры...")
    
    # Получаем токен бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
        print("Создайте файл .env и добавьте в него:")
        print("BOT_TOKEN=your_telegram_bot_token_here")
        return
    
    print("✅ BOT_TOKEN найден")
    
    # Проверяем OpenAI API ключ
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print("✅ OPENAI_API_KEY найден")
    else:
        print("⚠️ OPENAI_API_KEY не найден. Генерация изображений будет недоступна.")
    
    try:
        # Инициализация бота
        bot = Bot(
            token=bot_token, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        print("✅ Бот инициализирован")
        
        # Диспетчер
        dp = Dispatcher()
        
        # Подключаем роутеры
        dp.include_router(router)
        print("✅ Обработчики подключены")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"✅ Бот @{bot_info.username} готов к работе!")
        
        logger.info("Бот запущен успешно")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        try:
            await bot.session.close()
            print("🔄 Сессия бота закрыта")
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

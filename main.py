# main.py

import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from handlers import router
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

async def main():
    # Получаем токены из загруженных переменных
    bot_token = os.getenv("BOT_TOKEN")
    google_api_key = os.getenv("GOOGLE_API_KEY")

    # Проверяем, что оба ключа найдены
    if not bot_token:
        print("❌ BOT_TOKEN не найден. Убедитесь, что он есть в файле .env")
        return
    if not google_api_key:
        print("❌ GOOGLE_API_KEY не найден. Убедитесь, что он есть в файле .env")
        return

    bot = Bot(token=bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)

    print("🚀 Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


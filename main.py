# main.py
import asyncio
import logging
import base64
import httpx
from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile

# Если у вас есть еще обработчики, импортируйте их!
# from handlers import game_handlers, admin_handlers

load_dotenv()
BOT_TOKEN = getenv("BOT_TOKEN")
GEMINI_API_KEY = getenv("GEMINI_API_KEY")

# Асинхронная функция генерации изображения через Gemini
async def generate_image_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        # Путь к base64-картинке. Проверьте print(result) если не работает!
        image_base64 = result['candidates'][0]['content']['parts'][0]['inline_data']['data']
        return image_base64

# Создаем экземпляр aiogram Bot и Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Обработка команды/поиска для генерации картинки AI
@dp.message(F.text.regexp(r"картинка[:\-]?\s*(.*)", flags=0))
async def handle_image_generation(message: types.Message, regexp):
    prompt = regexp.group(1).strip() or "Случайная ситуация"
    await message.answer("Генерирую изображение через Google Gemini, пожалуйста подождите...")
    try:
        image_b64 = await generate_image_gemini(prompt)
        image_bytes = base64.b64decode(image_b64)
        await message.answer_photo(BufferedInputFile(image_bytes, filename="gemini-image.png"), caption=f'Запрос:\n<code>{prompt}</code>')
    except Exception as e:
        await message.answer(f"Ошибка при генерации изображения Gemini:\n<code>{e}</code>")

# Если у вас есть другие роутеры, подключайте здесь:
# dp.include_router(admin_handlers.router)
# dp.include_router(game_handlers.router)

async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

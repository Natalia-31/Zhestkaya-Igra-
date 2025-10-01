import aiohttp
from io import BytesIO
import google.generativeai as genai
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils import executor
from dotenv import load_dotenv

# ===== Настройка ключей =====
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция генерации картинки, возвращает BytesIO
async def generate_pollinations_image_file(scene_description: str) -> BytesIO | None:
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": scene_description}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=20) as response:
                if response.status == 200:
                    img_bytes = await response.read()
                    img_file = BytesIO(img_bytes)
                    img_file.name = "image.jpg"
                    img_file.seek(0)
                    return img_file
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
    return None

# Функция генерации шутки через Gemini
async def generate_card_joke(situation: str, answer: str) -> str:
    prompt = (
        f"Придумай короткую яркую шутку для карточной игры по ситуации: '{situation}', "
        f"и ответу игрока: '{answer}'. Язык русский, формат – мем, до 2 строк."
    )
    try:
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        text = response.text.strip() if response and response.text else "Шутка не получилась 🤷"
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
        text = "Шутка не сгенерировалась 🤷"
    return text

# Основная функция генерации и отправки
async def send_generated_card(chat_id: int, situation: str, answer: str):
    scene_desc = f"Cartoon style, humorous, minimalistic: {situation} with answer {answer}"
    
    image_file = await generate_pollinations_image_file(scene_desc)
    joke = await generate_card_joke(situation, answer)

    if image_file:
        await bot.send_photo(chat_id, photo=image_file, caption=joke)
    else:
        await bot.send_message(chat_id, f"Картинка не сгенерирована.\nШутка: {joke}")

# Пример команды для теста
@dp.message(Command("testcard"))
async def cmd_testcard(message: types.Message):
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми гостями"
    answer = "Я отклоняюсь назад и говорю, что это традиция моего народа"
    await send_generated_card(message.chat.id, situation, answer)

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))

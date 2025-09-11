import json, random, aiohttp, aiofiles, os
from pathlib import Path
from typing import Optional
from openai import AsyncOpenAI # Используем асинхронный клиент
from aiogram.types import FSInputFile
from aiogram import Bot

# Инициализируем клиент OpenAI с вашим ключом из переменных окружения
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json", images_dir: str = "generated_images"):
        self.situations_file = situations_file
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(exist_ok=True)
        self.situations = self._load_situations()

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str, image_id: Optional[str] = None) -> Optional[Path]:
        if not client.api_key:
            print("❌ OpenAI API ключ не найден.")
            return None
        try:
            # Новый синтаксис для генерации изображений
            response = await client.images.generate(
                model="dall-e-3", # или "dall-e-2"
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url
        except Exception as e:
            print(f"❌ Ошибка при генерации изображения OpenAI: {e}")
            return None

        # Скачиваем изображение
        output_path = self.images_dir / f"{image_id or random.randint(1000, 9999)}.png"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(output_path, mode='wb') as f:
                            await f.write(await resp.read())
                        return output_path
        except Exception as e:
            print(f"❌ Ошибка при скачивании изображения: {e}")
            return None
        return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if answer:
            prompt = f"Ситуация: {situation}. Ответ игрока: {answer}. Мультяшная яркая иллюстрация в стиле мемов."
        else:
            # Этот блок больше не используется, но оставлен для универсальности
            prompt = f"Ситуация: {situation}. Мультяшная яркая иллюстрация в стиле мемов."

        image_path = await self.generate_image_from_prompt(prompt, f"round_{chat_id}")
        if image_path:
            await bot.send_photo(chat_id, photo=FSInputFile(image_path))
            return True

        # Отправляем сообщение об ошибке только если генерация не удалась
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение. Проверьте консоль на наличие ошибок.")
        return False

# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()


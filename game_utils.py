import os
import json
import random
import aiohttp, aiofiles
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile

# OpenAI
from openai import AsyncOpenAI
# Gemini
import google.generativeai as genai

# Настройка клиентов
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class GameImageGenerator:
    def __init__(
        self,
        situations_file: str = "situations.json",
        images_dir: str = "generated_images",
        provider: str = "openai"  # <-- можно ставить "openai" или "gemini"
    ):
        self.situations_file = situations_file
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(exist_ok=True)
        self.situations = self._load_situations()
        self.provider = provider

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [
            "На вечеринке я неожиданно ___.",
            "Самая странная причина опоздать: ___.",
            "Мой секретный талант — ___."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def generate_image_from_prompt(self, prompt: str, image_id: Optional[str] = None) -> Optional[Path]:
        image_id = image_id or str(random.randint(1000, 9999))
        output_path = self.images_dir / f"{image_id}.png"

        if self.provider == "openai":
            try:
                response = await openai_client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                )
                image_url = response.data[0].url
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(output_path, mode="wb") as f:
                                await f.write(await resp.read())
                            return output_path
            except Exception as e:
                print(f"❌ Ошибка OpenAI: {e}")
                return None

        elif self.provider == "gemini":
            try:
                response = genai.generate_image(
                    model="imagen-3.0",  # или "imagen-2.1"
                    prompt=prompt,
                    size="1024x1024",
                    n=1
                )
                image_data = response.images[0]  # уже бинарные данные
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(image_data)
                return output_path
            except Exception as e:
                print(f"❌ Ошибка Gemini/Imagen: {e}")
                return None

        return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if answer:
            prompt = f"Ситуация: {situation}. Ответ игрока: {answer}. Мультяшная яркая иллюстрация в стиле мемов."
        else:
            prompt = f"Ситуация: {situation}. Мультяшная яркая иллюстрация в стиле мемов."

        image_path = await self.generate_image_from_prompt(prompt, f"round_{chat_id}")
        if image_path:
            await bot.send_photo(chat_id, photo=FSInputFile(image_path))
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
        return False


# Пример: переключаемся между провайдерами
gen = GameImageGenerator(provider="gemini")  # или provider="openai"

def get_random_situation() -> str:
    return gen.get_random_situation()

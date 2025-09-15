import json
import random
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Optional
import openai
from aiogram.types import FSInputFile
from aiogram import Bot
import os

class GameImageGenerator:
    def __init__(self,
                 situations_file: str = "situations.json",
                 images_dir: str = "generated_images"):
        self.situations_file = situations_file
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(exist_ok=True)
        self.situations = self._load_situations()

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
            except Exception:
                self.openai_client = None
                print("❌ Ошибка инициализации OpenAI клиента")
        else:
            self.openai_client = None
            print("⚠️ OPENAI_API_KEY не найден — генерация изображений недоступна")

    def _load_situations(self) -> List[str]:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
        # Резервные ситуации
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____.",
            "Лучшее оправдание для сна на работе: ____.",
            "Самое нелепое происшествие в школе: ____."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    async def generate_image_from_situation(self,
                                            situation: str,
                                            situation_id: Optional[str] = None) -> Optional[Path]:
        if not self.openai_client:
            return None
        prompt = (
            situation.replace("____", "неожиданная ситуация") +
            " — мультяшная, яркая иллюстрация"
        )
        try:
            resp = self.openai_client.images.generate(
                model="dall-e-3", prompt=prompt,
                size="1024x1024", n=1)
            url = resp.data[0].url
        except Exception:
            return None

        filename = situation_id or f"situation_{random.randint(1000,9999)}"
        out_path = self.images_dir / f"{filename}.png"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    if r.status == 200:
                        async with aiofiles.open(out_path, "wb") as f:
                            async for chunk in r.content.iter_chunked(8192):
                                await f.write(chunk)
                        return out_path
        except Exception:
            return None

        return None

    async def send_situation_with_image(self,
                                        bot: Bot,
                                        chat_id: int) -> bool:
        sit = self.get_random_situation()
        await bot.send_message(chat_id, f"🎲 Ситуация:\n\n_{sit}_",
                               parse_mode="Markdown")
        img = await self.generate_image_from_situation(sit)
        if img and img.exists():
            await bot.send_photo(chat_id, photo=FSInputFile(img))
            return True
        else:
            await bot.send_message(chat_id,
                                   "⚠️ Не удалось сгенерировать изображение.")
            return False

gen = GameImageGenerator()

async def send_random_situation_with_image(bot: Bot, chat_id: int) -> bool:
    return await gen.send_situation_with_image(bot, chat_id)

def get_random_situation() -> str:
    return gen.get_random_situation()

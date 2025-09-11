import json, random, aiohttp, aiofiles, os
from pathlib import Path
from typing import List, Optional
import openai
from aiogram.types import FSInputFile
from aiogram import Bot

openai.api_key = os.getenv("OPENAI_API_KEY")

class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json", images_dir: str = "generated_images"):
        self.situations_file = situations_file
        self.images_dir = Path(images_dir); self.images_dir.mkdir(exist_ok=True)
        self.situations = self._load_situations()

    def _load_situations(self) -> List[str]:
        try:
            data = json.load(open(self.situations_file, encoding="utf-8"))
            if isinstance(data, list) and data: return data
        except: pass
        return ["На вечеринке я неожиданно ____.","Самая странная причина опоздать: ____.",
                "Мой секретный талант — ____.","Лучшее оправдание для сна на работе: ____.","Самое нелепое происшествие в школе: ____."]
    def get_random_situation(self) -> str:
        import random; return random.choice(self.situations)

    async def generate_image_from_situation(self, prompt: str, situation_id: Optional[str]=None) -> Optional[Path]:
        if not openai.api_key: return None
        try:
            resp = openai.Image.create(prompt=prompt, n=1, size="1024x1024")
            url = resp["data"][0]["url"]
        except: return None
        out = self.images_dir / f"{situation_id or random.randint(1000,9999)}.png"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as r:
                    if r.status==200:
                        f = await aiofiles.open(out,"wb")
                        async for ch in r.content.iter_chunked(8192): await f.write(ch)
                        await f.close(); return out
        except: return None
        return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str]=None) -> bool:
        if answer:
            prompt = f"Ситуация: {situation}. Ответ игрока: {answer}. Мультяшная яркая иллюстрация."
        else:
            prompt = f"Ситуация: {situation}. Мультяшная яркая иллюстрация."
        img = await self.generate_image_from_situation(prompt, f"round_{chat_id}")
        if img:
            await bot.send_photo(chat_id, photo=FSInputFile(img))
            return True
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")
        return False

gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

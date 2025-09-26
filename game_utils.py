# game_utils.py
import os
import json
import random
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# ====== Загрузка ключей ======
load_dotenv()
NANO_API_KEY   = os.getenv("NANO_API_KEY")
HORDE_API_KEY  = os.getenv("HORDE_API_KEY")
POLLO_API_KEY  = os.getenv("POLLO_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ====== Менеджер колод ======
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json", base: Path | None = None):
        self.base_dir = base or Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path)
        self.answers: List[str]    = self._load_list(self.ans_path)

    def _load_list(self, file_path: Path) -> List[str]:
        for enc in ("utf-8-sig", "utf-8"):
            try:
                data = json.loads(file_path.read_text(encoding=enc))
                if isinstance(data, list):
                    seen, out = set(), []
                    for x in data:
                        if isinstance(x, str):
                            x = x.strip()
                            if x and x not in seen:
                                seen.add(x); out.append(x)
                    return out
                return []
            except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
                continue
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Тестовая ситуация"

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = list(self.answers)
        random.shuffle(deck)
        return deck

# ====== Генерация изображения через Pollinations ======
async def generate_pollinations_image(scene_description: str) -> Optional[str]:
    url = f"https://image.pollinations.ai/prompt/{quote(scene_description)}?width=768&height=432"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=20) as r:
            if r.status == 200:
                return str(r.url)
    return None

# ====== Gemini (шутка + описание сцены) ======
import google.generativeai as genai
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
else:
    gemini_model = None

async def generate_card_content(situation: str, answer: str):
    if not gemini_model:
        return None, "⚠️ GEMINI_API_KEY не найден"

    # 1. описание сцены
    scene_prompt = (
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Сделай короткое (1–2 предложения) описание визуальной сцены для картинки."
        "Стиль: абсурдный, ироничный, как для настольной карточной игры. Без текста на самой картинке."
    )
    scene_desc = (await asyncio.to_thread(gemini_model.generate_content, scene_prompt)).text.strip()

    # 2. картинка
    image_url = await generate_pollinations_image(scene_desc)

    # 3. шутка
    joke_prompt = (
        f"Придумай смешную подпись для карточной игры.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Формат: мем, максимум 2 строки, на русском."
    )
    joke = (await asyncio.to_thread(gemini_model.generate_content, joke_prompt)).text.strip()

    return image_url, joke

# ====== Экземпляры ======
decks = DeckManager(base=Path(__file__).resolve().parent)

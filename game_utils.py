import json
import random
from pathlib import Path
from io import BytesIO
import asyncio
import aiohttp

from dotenv import load_dotenv
load_dotenv()

import os
from aiogram import Bot
from aiogram.types import BufferedInputFile

NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
POLLO_API_KEY = os.getenv("POLLO_API_KEY")


class DeckManager:
    def __init__(self,
                 sit_file="situations.json",
                 ans_file="answers.json"):
        # Корень проекта
        base = Path(__file__).parent.parent
        self.situations = self._load(base / sit_file)
        self.answers    = self._load(base / ans_file)

    def _load(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Нет ситуаций"

    def get_new_shuffled_answers_deck(self):
        deck = self.answers.copy() if self.answers else []
        random.shuffle(deck)
        return deck


decks = DeckManager(
    sit_file="situations.json",
    ans_file="answers.json"
)


async def send_illustration(bot: Bot, chat_id: int, situation: str, answer: str) -> bool:
    prompt = f"{situation} — {answer}, cartoon style, simple shapes"
    img = await _try_horde(prompt) or await _try_nanobanana(prompt)
    if img:
        img.seek(0)
        await bot.send_photo(chat_id,
                             photo=BufferedInputFile(img.read(), filename="scene.png"))
        return True
    return False

# ... остальной код без изменений ...

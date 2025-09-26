# game_utils.py — обновлённая версия
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

import google.generativeai as genai

# ====== Загрузка ключей ======
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")
else:
    gemini_model = None

# ====== Менеджер колод ======
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json", base: Path | None = None):
        self.base_dir = base or Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str]    = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
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

# ====== Генерация описания сцены ======
async def generate_scene_prompt(situation: str, answer: str) -> str:
    if not gemini_model:
        return f"Cartoon of '{situation}' with answer '{answer}'"

    prompt = (
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Составь конкретное визуальное описание сцены. "
        "Укажи минимум два объекта (например: человек, животное, предмет). "
        "Добавь действие или реакцию. "
        "Не используй слова 'сцена', 'кадр', 'иллюстрация'. "
        "Стиль: мем, карикатура, comic panel, colorful, exaggerated expressions."
    )
    response = await asyncio.to_thread(gemini_model.generate_content, prompt)
    return response.text.strip()

# ====== Генерация картинки через Pollinations ======
async def generate_pollinations_image(scene_description: str) -> Optional[str]:
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": scene_description}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, timeout=20) as r:
                if r.status == 200:
                    return str(r.url)
    except Exception:
        pass
    return None

# ====== Генерация шутки ======
async def generate_card_joke(situation: str, answer: str) -> str:
    if not gemini_model:
        return f"Ситуация: {situation} | Ответ: {answer}"

    prompt = (
        f"Придумай короткую смешную подпись.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Формат: мем, максимум 2 строки, на русском."
    )
    response = await asyncio.to_thread(gemini_model.generate_content, prompt)
    return response.text.strip()

# ====== Основная функция ======
async def generate_card_content(situation: str, answer: str):
    scene_description = await generate_scene_prompt(situation, answer)
    image_url = await generate_pollinations_image(scene_description)
    joke_text = await generate_card_joke(situation, answer)
    return image_url, joke_text

# ====== Экземпляры ======
decks = DeckManager(base=Path(__file__).resolve().parent)

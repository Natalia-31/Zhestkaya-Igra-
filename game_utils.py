import os
import json
import random
from pathlib import Path
from typing import List, Optional
import asyncio
import aiohttp
from dotenv import load_dotenv
import google.generativeai as genai

# ====== Загрузка ключей ======
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

# Менеджер колод
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
                                seen.add(x)
                                out.append(x)
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

# Генерация картинки через Pollinations на основе ситуации и ответа
async def generate_pollinations_image(situation: str, answer: str) -> Optional[str]:
    prompt = (
        f"Cartoon style card for a Russian Telegram game 'Жесткая игра': Situation: {situation}, "
        f"Player's answer: {answer}. Minimalism, humor, bold lines, no text overlay on the image itself."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=20) as resp:
                if resp.status == 200:
                    # Pollinations возвращает редирект на сгенерированное изображение
                    return str(resp.url)
    except Exception as e:
        print(f"Ошибка генерации изображения Pollinations: {e}")
    return None

# Генерация шутки через Gemini API
async def generate_card_joke(situation: str, answer: str) -> str:
    if not gemini_model:
        return f"Ситуация: {situation} | Ответ: {answer}"
    prompt = (
        f"Придумай короткую смешную подпись.\n"
        f"Ситуация: {situation}\n"
        f"Ответ игрока: {answer}\n"
        "Формат: мем, максимум 2 строки, на русском."
    )
    try:
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
        return "Не удалось сгенерировать шутку."

# Основная функция генерации карточного контента
async def generate_card_content(situation: str, answer: str):
    image_url = await generate_pollinations_image(situation, answer)
    joke_text = await generate_card_joke(situation, answer)
    return image_url, joke_text

# Инициализация менеджера колод
decks = DeckManager(base=Path(__file__).resolve().parent)

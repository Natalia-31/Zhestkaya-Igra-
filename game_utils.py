import os
import json
import random
from pathlib import Path
from typing import List, Optional
import asyncio
from dotenv import load_dotenv

from perplexity import Perplexity
import google.generativeai as genai

# ====== Загрузка ключей из .env ======
load_dotenv()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # твой ключ Perplexity
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")          # твой ключ Gemini
genai.configure(api_key=GEMINI_API_KEY)

perplexity_client = Perplexity(api_key=PERPLEXITY_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

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

# ====== Генерация карточки изображения через Perplexity ======
async def generate_perplexity_card_image(situation: str) -> Optional[str]:
    prompt = (
        f"Create a stylish Telegram game card for the game 'Жесткая игра'. "
        f"Show the situation text prominently in a bold, readable font: \"{situation}\". "
        f"Use bright colors and modern design with the game logo in the corner. "
        f"The card should look fun, attractive, and clear."
    )
    try:
        response = await perplexity_client.chat.completions.create(
            model="gpt-image-1",
            messages=[{"role": "user", "content": prompt}],
        )
        for choice in response.choices:
            content = choice.message.content
            if isinstance(content, dict) and "image_url" in content:
                return content["image_url"]["url"]
    except Exception as e:
        print(f"Error generating Perplexity card image: {e}")
    return None

# ====== Генерация шутки через Gemini ======
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

# ====== Основная генерация карточного контента ======
async def generate_card_content(situation: str, answer: str):
    image_url = await generate_perplexity_card_image(situation)
    joke_text = await generate_card_joke(situation, answer)
    return image_url, joke_text

# ====== Инициализация менеджера колод ======
decks = DeckManager(base=Path(__file__).resolve().parent)

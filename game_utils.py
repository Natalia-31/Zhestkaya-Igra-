# game_utils.py - ЧИСТАЯ ВЕРСИЯ

import os
import json
import random

# --- Класс для управления колодами ---
class DeckManager:
    def __init__(self, situations_file="situations.json", answers_file="answers.json"):
        self.situations = self._load_deck(situations_file)
        self.answers = self._load_deck(answers_file)

    def _load_deck(self, filename: str) -> list:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(script_dir, filename)
            with open(full_path, "r", encoding="utf-8") as f:
                deck = json.load(f)
            if isinstance(deck, list) and deck:
                print(f"✅ Колода '{filename}' успешно загружена: {len(deck)} карт.")
                return deck
            return []
        except Exception as e:
            # Теперь ошибка кодировки будет явно видна здесь
            print(f"❌ ОШИБКА при загрузке '{filename}': {e}")
            return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Ситуации не найдены."

    def get_new_shuffled_answers_deck(self) -> list:
        deck_copy = self.answers.copy()
        random.shuffle(deck_copy)
        return deck_copy

# --- Класс для генерации изображений ---
# Вставьте сюда ВЕСЬ ваш класс GameImageGenerator со всеми импортами для него
# (aiohttp, BytesIO, load_dotenv, Bot, BufferedInputFile и т.д.)
# Я его пока уберу, чтобы не загромождать ответ, но он должен быть здесь.
class GameImageGenerator:
    # ... Ваш полный класс для генерации изображений ...
    pass

# --- ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ---
# Создаем экземпляры, которые будут импортироваться в другие файлы
decks = DeckManager()
gen = GameImageGenerator()

# game_utils.py — ситуации/ответы из JSON + генерация изображений по HTTP (без сторонних SDK)

import json
import random
from pathlib import Path
from typing import List, Optional

import aiohttp
import aiofiles
from aiogram import Bot
from aiogram.types import FSInputFile


class DeckManager:
    """
    Загружает situations.json и answers.json (UTF-8 и UTF-8-SIG),
    отдаёт случайную ситуацию и перемешанную колоду ответов.
    """
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()

        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        # Пытаемся прочесть как UTF-8, затем как UTF-8-SIG (BOM)
        for enc in ("utf-8", "utf-8-sig"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)  # json.load на уже открытому файлу [14]
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc}): {len(data)} из {file_path}")  # [17]
                    return data
                else:
                    print(f"⚠️ {file_path} ({label}) не содержит JSON-список")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path} ({label})")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Кодировка {enc} не подошла: {e} — пробуем следующую…")  # [20]
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в {file_path} ({label}): {e}")  # [14]
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка при чтении {file_path} ({label}): {e}")
                return []
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "На вечеринке я неожиданно ____."

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck


class GameImageGenerator:
    """
    Генерация без OpenAI: скачиваем картинку по публичному URL (Pollinations).
    Никаких import pollinations — только чистый HTTP через aiohttp.
    """
    def __init__(self, images_dir: str = "generated_images"):
        self.base_dir = Path(__file__).resolve().parent
        self.images_dir = (self.base_dir / images_dir).resolve()
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = aiohttp.ClientTimeout(total=120)

    def _build_prompt(self, situation: str, answer: Optional[str]) -> str:
        base = situation.replace("____", answer or "неожиданный поворот")
        # Короткий стабильный промпт
        return f"{base}, cartoon, vibrant, colorful, high quality"

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        from urllib.parse import quote
        prompt = self._build_prompt(situation, answer)
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"  # прямой URL, без Python-пакета [5]

        out_path = self.images_dir / f"img_{random.randint(1000,9999)}.png"
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200 and (resp.headers.get("Content-Type", "").startswith("image/")):
                        async with aiofiles.open(out_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):  # потоковая запись [3][9]
                                await f.write(chunk)
                        await bot.send_photo(chat_id, FSInputFile(out_path))  # отправка файла из FS [7][13]
                        return True
                    else:
                        print(f"⚠️ HTTP {resp.status} от генератора, content-type={resp.headers.get('Content-Type')}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки изображения: {e}")
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение.")  # [13]
        return False


# Экспорт для хэндлеров
decks = DeckManager()
gen = GameImageGenerator()

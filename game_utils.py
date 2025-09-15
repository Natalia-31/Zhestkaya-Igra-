# game_utils.py — Полностью обновлённый с create_prompt, _load_list и send_illustration без подписи

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

# ========== Загрузка ключей ==========
load_dotenv()
NANO_API_KEY = os.getenv("NANO_API_KEY")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# ========== Функция для создания промпта ==========
def create_prompt(situation: str, answer: str) -> str:
    """Создает детальный промпт с контекстом для лучшей генерации."""
    translations = {
        "Меня взяли на работу, потому что я умею": "I got hired because I can",
        "Лучшее оправдание для сна на работе": "Best excuse for sleeping at work",
        "Если бы суперсила выбирала меня": "If I had a superpower it would be",
        "Самое нелепое происшествие в школе": "Most ridiculous thing that happened at school",
        "Идеальный подарок на день рождения": "Perfect birthday gift",
        "Мой секретный талант": "My secret talent",
        "То, что точно не стоит писать в резюме": "Something you should never put in your resume",
        "Главный кулинарный шедевр моего детства": "My greatest childhood cooking masterpiece",
        "бесконечный запас пельменей": "infinite supply of dumplings",
        "говорящий кактус": "talking cactus",
        "очень злой хомяк": "very angry hamster",
        "квантовый двигатель от жигулей": "quantum engine from old Russian car",
        "армия боевых пингвинов": "army of combat penguins",
        "потерянные носки": "lost socks from another dimension",
        "секретная база на Луне": "secret moon base",
        "грустный тромбон": "sad trombone",
        "кибер-бабушка с лазерными глазами": "cyber grandma with laser eyes",
        "дракон, работающий бухгалтером": "dragon working as accountant",
        "невидимый велосипед": "invisible bicycle",
        "портал в страну розовых пони": "portal to pink pony land",
        "картофельное ополчение": "potato militia",
        "забытый пароль от Вселенной": "forgotten password to the Universe",
        "робот-пылесос, захвативший мир": "robot vacuum that conquered the world",
        "философский камень": "philosopher's stone that turned out to be regular pebble",
        "енот, ворующий мемы": "raccoon stealing memes",
        "подозрительно умный голубь": "suspiciously smart pigeon",
        "котенок, который случайно запустил ядерные ракеты": "kitten who accidentally launched nuclear missiles"
    }
    situation_en = situation.replace("____", "").strip()
    for ru, en in translations.items():
        if ru in situation_en:
            situation_en = situation_en.replace(ru, en)
            break
    answer_en = answer.strip()
    for ru, en in translations.items():
        if ru in answer_en:
            answer_en = en
            break
    if any(ord(c) > 127 for c in situation_en):
        try:
            from googletrans import Translator
            situation_en = Translator().translate(situation_en, dest='en').text
        except:
            pass
    if any(ord(c) > 127 for c in answer_en):
        try:
            from googletrans import Translator
            answer_en = Translator().translate(answer_en, dest='en').text
        except:
            pass
    scene_description = f"{situation_en} {answer_en}"
    style_modifiers = [
        "funny cartoon illustration",
        "humorous scene",
        "absurd comedy",
        "whimsical digital art",
        "colorful and vibrant",
        "comedic situation",
        "high quality illustration",
        "detailed funny scene"
    ]
    final_prompt = f"{scene_description}, {', '.join(style_modifiers)}"
    print(f"📝 [Финальный промпт] {final_prompt}")
    return final_prompt

# ========== Менеджер колод ==========
class DeckManager:
    def __init__(self, situations_file: str = "situations.json", answers_file: str = "answers.json"):
        self.base_dir = Path(__file__).resolve().parent
        self.sit_path = (self.base_dir / situations_file).resolve()
        self.ans_path = (self.base_dir / answers_file).resolve()
        self.situations: List[str] = self._load_list(self.sit_path, "situations")
        self.answers: List[str] = self._load_list(self.ans_path, "answers")

    def _load_list(self, file_path: Path, label: str) -> List[str]:
        # Выводим для отладки, существует ли файл и где он
        print(f"🔍 Loading '{label}' from {file_path} (exists={file_path.exists()})")
        for enc in ("utf-8-sig", "utf-8"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"✅ Колода '{label}' загружена ({enc}): {len(data)} items")
                    return data
                else:
                    print(f"⚠️ {file_path} ({label}) не содержит JSON-список")
                    return []
            except FileNotFoundError:
                print(f"❌ Файл не найден: {file_path}")
                return []
            except UnicodeDecodeError as e:
                print(f"⚠️ Кодировка {enc} не подошла: {e}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON ошибка ({enc}) в {file_path}: {e}")
                return []
            except Exception as e:
                print(f"❌ Неожиданная ошибка ({enc}) при чтении {file_path}: {e}")
        print(f"⚠️ Не удалось загрузить '{label}' из {file_path} ни с одной кодировкой")
        return []

    def get_random_situation(self) -> str:
        return random.choice(self.situations) if self.situations else "Если бы не ____, я бы бросил пить."

    def get_new_shuffled_answers_deck(self) -> List[str]:
        deck = self.answers.copy()
        random.shuffle(deck)
        return deck

decks = DeckManager()

# ========== Генератор изображений ==========
class GameImageGenerator:
    def __init__(self):
        self.nb_key = NANO_API_KEY
        self.nb_url = "https://api.nanobanana.ai/v1/generate"
        self.horde_key = HORDE_API_KEY
        self.horde_url = "https://aihorde.net/api/v2"

    async def _try_pollinations(self, prompt: str) -> Optional[BytesIO]:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=512&height=512"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=15) as r:
                    if r.status == 200:
                        return BytesIO(await r.read())
        except:
            pass
        return None

    async def _try_nanobanana(self, prompt: str) -> Optional[BytesIO]:
        if not self.nb_key:
            return None
        payload = {
            "prompt": prompt,
            "model": "sdxl",
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg_scale": 7.0
        }
        headers = {"Authorization": f"Bearer {self.nb_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(self.nb_url, json=payload, headers=headers, timeout=40) as r:
                    if r.status == 200:
                        data = await r.json()
                        img_url = data.get("image_url")
                        if img_url:
                            async with s.get(img_url, timeout=20) as ir:
                                if ir.status == 200:
                                    return BytesIO(await ir.read())
        except:
            pass
        return None

    async def send_illustration(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if not answer:
            await bot.send_message(chat_id, "⚠️ Нет ответа для генерации изображения.")
            return False

        prompt = create_prompt(situation, answer)
        tasks = [
            self._try_pollinations(prompt),
            self._try_nanobanana(prompt),
        ]
        for future in asyncio.as_completed(tasks):
            try:
                img_buf = await future
                if img_buf:
                    await bot.send_photo(
                        chat_id,
                        photo=BufferedInputFile(file=img_buf.read(), filename="game_scene.jpg")
                    )
                    return True
            except:
                continue

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение по вашей ситуации.")
        return False

gen = GameImageGenerator()

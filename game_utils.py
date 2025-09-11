# game_utils.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ AI HORDE

import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
import base64

from aiogram import Bot
from aiogram.types import BufferedInputFile


class GameImageGenerator:
    def __init__(self, situations_file: str = "situations.json"):
        self.situations_file = situations_file
        self.situations = self._load_situations()
        # AI Horde API настройки
        self.api_key = "0000000000"  # Анонимный ключ
        self.base_url = "https://aihorde.net/api/v2"

    def _load_situations(self) -> list:
        try:
            with open(self.situations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return [
            "На вечеринке я неожиданно ____.",
            "Самая странная причина опоздать: ____.",
            "Мой секретный талант — ____.",
            "В ресторане я случайно ____.",
            "На работе меня застали за ____.",
            "Дома я обнаружил, что мой холодильник ____."
        ]

    def get_random_situation(self) -> str:
        return random.choice(self.situations)

    def create_optimized_prompt(self, situation: str, answer: str) -> str:
        """
        Создает грамматически правильный промпт для AI Horde
        """
        # Убираем прочерки и очищаем текст
        combined_text = situation.replace("____", answer).strip()
        
        # Расширенный словарь для качественного перевода
        translations = {
            # Места
            "На вечеринке": "At a party",
            "в ресторане": "in a restaurant", 
            "дома": "at home",
            "на работе": "at work",
            "в магазине": "in a store",
            "на улице": "on the street",
            "в школе": "at school",
            "в кино": "at the cinema",
            
            # Начальные фразы
            "Мой секретный талант — ": "My secret talent is ",
            "Самая странная причина": "The strangest reason",
            "Самая распространенная причина": "The most common reason",
            
            # Действия и глаголы
            "я неожиданно": "I unexpectedly",
            "я случайно": "I accidentally", 
            "меня застали за": "I was caught",
            "я обнаружил": "I discovered",
            "опоздать": "being late",
            "проснуться": "waking up",
            "упал в": "fell into",
            "упал": "fell down",
            "танцевать": "dancing",
            "петь": "singing",
            "кричать": "shouting",
            "плакать": "crying",
            "смеяться": "laughing",
            "бежать": "running",
            "прыгать": "jumping",
            
            # Предметы
            "холодильник": "refrigerator",
            "торт": "cake",
            "кот в сапогах": "Puss in Boots",
            "собака": "dog",
            "кот": "cat",
            "птица": "bird",
            "стол": "table",
            "стул": "chair"
        }
        
        # Применяем переводы по порядку (сначала длинные фразы, потом короткие)
        english_text = combined_text
        for ru_phrase in sorted(translations.keys(), key=len, reverse=True):
            english_text = english_text.replace(ru_phrase, translations[ru_phrase])
        
        # Если остались русские символы, используем автоперевод
        if any(ord(char) > 127 for char in english_text):
            try:
                from googletrans import Translator
                translator = Translator()
                translation = translator.translate(combined_text, dest='en')
                english_text = translation.text
                print(f"🔄 Переведено: {combined_text} -> {english_text}")
            except Exception as e:
                print(f"⚠️ Ошибка автоперевода: {e}")
                # Оставляем как есть с частичными переводами
        
        # Убираем лишние знаки препинания и пробелы
        english_text = english_text.replace(".", "").replace(",", "").strip()
        
        # Создаем финальный промпт БЕЗ лишних запятых
        prompt = f"{english_text} masterpiece best quality highly detailed photorealistic cinematic lighting"
        
        return prompt.strip()

    async def generate_image_with_horde(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через AI Horde API с улучшенной обработкой ошибок
        """
        print(f"🤖 AI Horde: Отправляю запрос с промптом: {prompt}")
        
        # Упрощенные параметры для AI Horde
        payload = {
            "prompt": prompt,
            "params": {
                "sampler_name": "k_euler",
                "cfg_scale": 7.0,
                "height": 512,
                "width": 512,
                "steps": 20,
                "n": 1
            },
            "nsfw": False,
            "trustedworkers": True,
            "models": ["AlbedoBase XL (SDXL)"],  # Стабильная модель
            "r2": True,
            "shared": False,
            "replacement_filter": True,
            "dry_run": False
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key,
            "User-Agent": "TelegramBot/1.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Шаг 1: Отправляем запрос на генерацию
                async with session.post(f"{self.base_url}/generate/async", 
                                      json=payload, headers=headers) as response:
                    
                    response_text = await response.text()
                    print(f"🔍 AI Horde ответ: статус {response.status}, текст: {response_text}")
                    
                    if response.status != 202:
                        print(f"❌ AI Horde: Ошибка при отправке запроса: {response.status}")
                        print(f"❌ Детали ошибки: {response_text}")
                        return None
                    
                    try:
                        result = await response.json()
                    except:
                        print(f"❌ AI Horde: Не удалось парсить JSON ответ")
                        return None
                    
                    job_id = result.get("id")
                    
                    if not job_id:
                        print("❌ AI Horde: Не получен ID задания")
                        return None
                    
                    print(f"🔄 AI Horde: Задание создано с ID: {job_id}")

                # Шаг 2: Ждем завершения генерации
                max_attempts = 40  # Максимум 3.5 минуты ожидания
                for attempt in range(max_attempts):
                    await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                    
                    async with session.get(f"{self.base_url}/generate/check/{job_id}") as check_response:
                        if check_response.status != 200:
                            continue
                            
                        check_result = await check_response.json()
                        
                        if check_result.get("done", False):
                            generations = check_result.get("generations", [])
                            if generations and generations[0].get("img"):
                                # Декодируем base64 изображение
                                img_base64 = generations[0]["img"]
                                img_bytes = base64.b64decode(img_base64)
                                print("✅ AI Horde: Изображение успешно сгенерировано")
                                return BytesIO(img_bytes)
                            else:
                                print("❌ AI Horde: Генерация завершена, но изображение не получено")
                                return None
                        
                        # Показываем прогресс
                        queue_position = check_result.get("queue_position", "?")
                        wait_time = check_result.get("wait_time", "?")
                        print(f"⏳ AI Horde: Позиция в очереди: {queue_position}, ожидание: {wait_time}с")

                print("❌ AI Horde: Превышено время ожидания")
                return None

        except Exception as e:
            print(f"❌ AI Horde: Критическая ошибка: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        """
        Генерирует и отправляет изображение с улучшенной обработкой ошибок
        """
        if answer:
            prompt = self.create_optimized_prompt(situation, answer)
        else:
            # Простой fallback промпт
            prompt = f"A photorealistic image masterpiece best quality"

        print(f"📝 Финальный промпт: {prompt}")

        # Используем AI Horde
        image_bytes_io = await self.generate_image_with_horde(prompt)

        if image_bytes_io:
            try:
                await bot.send_photo(
                    chat_id,
                    photo=BufferedInputFile(file=image_bytes_io.read(), filename="generated_image.jpeg"),
                    caption=f"🎨 Промпт: {prompt}"
                )
                return True
            except Exception as e:
                print(f"❌ Ошибка при отправке изображения в Telegram: {e}")
                return False

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение через AI Horde. Сервис может быть перегружен, попробуйте позже.")
        return False


# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

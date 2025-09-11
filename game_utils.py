# game_utils.py - ВЕРСИЯ С AI HORDE

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
        self.api_key = "0000000000"  # Анонимный ключ, можно заменить на свой
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
        Создает оптимизированный промпт для AI Horde
        """
        # Объединяем ситуацию с ответом
        combined_text = situation.replace("____", answer).strip()
        
        # Словарь для перевода
        translations = {
            "На вечеринке": "At a party",
            "в ресторане": "in a restaurant", 
            "дома": "at home",
            "на работе": "at work",
            "в магазине": "in a store",
            "на улице": "on the street",
            "Мой секретный талант": "My secret talent is",
            "Самая странная причина": "The strangest reason",
            "Самая распространенная причина": "The most common reason",
            "опоздать": "to be late",
            "холодильник": "refrigerator",
            "кот в сапогах": "puss in boots"
        }
        
        # Применяем переводы
        english_text = combined_text
        for ru, en in translations.items():
            english_text = english_text.replace(ru, en)
        
        # Если остался русский текст, используем полный перевод
        if any(ord(char) > 127 for char in english_text):
            try:
                from googletrans import Translator
                translator = Translator()
                translation = translator.translate(combined_text, dest='en')
                english_text = translation.text
            except:
                english_text = combined_text  # Fallback
        
        # Создаем промпт, оптимизированный для AI Horde
        prompt = f"{english_text}, masterpiece, best quality, highly detailed, photorealistic, cinematic lighting"
        
        return prompt.strip()

    async def generate_image_with_horde(self, prompt: str) -> Optional[BytesIO]:
        """
        Генерирует изображение через AI Horde API
        """
        print(f"🤖 AI Horde: Отправляю запрос с промптом: {prompt}")
        
        # Параметры запроса для AI Horde
        payload = {
            "prompt": prompt,
            "params": {
                "sampler_name": "k_dpmpp_2m",
                "cfg_scale": 7.5,
                "denoising_strength": 1.0,
                "seed": "",
                "height": 512,
                "width": 512,
                "seed_variation": 1,
                "post_processing": [],
                "karras": True,
                "tiling": False,
                "hires_fix": False,
                "clip_skip": 1,
                "control_type": None,
                "image_is_control": False,
                "return_control_map": False,
                "facefixer_strength": 0.75,
                "loras": [],
                "tis": [],
                "special": {},
                "steps": 25,
                "n": 1
            },
            "nsfw": False,
            "trustedworkers": True,
            "models": ["Deliberate"],  # Можно добавить: "FLUX.1-dev", "SDXL", etc
            "r2": True,
            "shared": False,
            "replacement_filter": True,
            "dry_run": False,
            "proxied_account": None,
            "disable_batching": False
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Шаг 1: Отправляем запрос на генерацию
                async with session.post(f"{self.base_url}/generate/async", 
                                      json=payload, headers=headers) as response:
                    if response.status != 202:
                        print(f"❌ AI Horde: Ошибка при отправке запроса: {response.status}")
                        return None
                    
                    result = await response.json()
                    job_id = result.get("id")
                    
                    if not job_id:
                        print("❌ AI Horde: Не получен ID задания")
                        return None
                    
                    print(f"🔄 AI Horde: Задание создано с ID: {job_id}")

                # Шаг 2: Ждем завершения генерации
                max_attempts = 60  # Максимум 5 минут ожидания
                for attempt in range(max_attempts):
                    await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                    
                    async with session.get(f"{self.base_url}/generate/check/{job_id}") as check_response:
                        if check_response.status != 200:
                            continue
                            
                        check_result = await check_response.json()
                        
                        if check_result.get("done", False):
                            generations = check_result.get("generations", [])
                            if generations and generations.get("img"):
                                # Декодируем base64 изображение
                                img_base64 = generations["img"]
                                img_bytes = base64.b64decode(img_base64)
                                print("✅ AI Horde: Изображение успешно сгенерировано")
                                return BytesIO(img_bytes)
                        
                        print(f"⏳ AI Horde: Ожидание... Попытка {attempt + 1}/{max_attempts}")

                print("❌ AI Horde: Превышено время ожидания")
                return None

        except Exception as e:
            print(f"❌ AI Horde: Ошибка при генерации: {e}")
            return None

    async def generate_and_send_image(self, bot: Bot, chat_id: int, situation: str, answer: Optional[str] = None) -> bool:
        if answer:
            prompt = self.create_optimized_prompt(situation, answer)
        else:
            prompt = f"{situation}, masterpiece, best quality"

        # Используем AI Horde вместо pollinations.ai
        image_bytes_io = await self.generate_image_with_horde(prompt)

        if image_bytes_io:
            await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(file=image_bytes_io.read(), filename="image.jpeg"),
                caption=f"🎨 AI Horde промпт: {prompt}"
            )
            return True

        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать изображение через AI Horde. Попробуйте позже.")
        return False


# Глобальный экземпляр
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

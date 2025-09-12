# game_utils.py - ВЕРСИЯ С ПЕРЕЗАГРУЗКОЙ

import os
import json
import random
from typing import Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# ... (ваш код для create_prompt и загрузки API-ключей остается здесь) ...
# Я его убрал для краткости, но он должен остаться в вашем файле

class GameImageGenerator:
    def __init__(self, situations_file="situations.json"):
        self.situations_file = situations_file
        # Убеждаемся, что путь к файлу правильный, относительно текущего скрипта
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.full_path_to_situations = os.path.join(base_dir, self.situations_file)
        
        self.situations = self._load_situations()

    def _load_situations(self) -> list:
        """Надежно загружает ситуации из файла."""
        default_situations = ["Резервная ситуация: На вечеринке я неожиданно ____."]
        try:
            with open(self.full_path_to_situations, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            
            if isinstance(loaded_data, list) and loaded_data:
                print(f"✅ Успешно загружено {len(loaded_data)} ситуаций.")
                return loaded_data
            else:
                print("⚠️ Файл с ситуациями пуст. Используется резервный список.")
                return default_situations
                
        except FileNotFoundError:
             print(f"❌ Файл {self.situations_file} не найден. Используется резервный список.")
             return default_situations
        except Exception as e:
            print(f"❌ Ошибка при чтении файла: {e}. Используется резервный список.")
            return default_situations

    def reload_situations(self) -> int:
        """Перезагружает ситуации из файла и возвращает их количество."""
        self.situations = self._load_situations()
        return len(self.situations)

    def get_random_situation(self) -> str:
        """Возвращает случайную ситуацию из загруженного списка."""
        if not self.situations:
            # Эта проверка на всякий случай, если даже резервный список будет пустым
            return "Резервная ситуация: На вечеринке я неожиданно ____."
        return random.choice(self.situations)

    # ... (весь ваш код для генерации изображений _try_nanobanana, _try_horde и т.д. остается здесь) ...

# Глобальный экземпляр для доступа из других файлов
gen = GameImageGenerator()

def get_random_situation() -> str:
    return gen.get_random_situation()

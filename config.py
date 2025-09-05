"""
Конфигурация бота
"""
import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID администраторов (можно указать через запятую: 123456,234567,...)
ADMIN_IDS: List[int] = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

# Настройки игры
GAME_SETTINGS = {
    "max_players": 10,
    "cards_per_hand": 10,
    "round_timeout": 120,  # секунд
    "min_players": 3,
}

# База данных
DATABASE_URL = "database/game.db"

# Настройки изображений
IMAGE_SETTINGS = {
    "enabled": True,
    "dalle_api_key": os.getenv("OPENAI_API_KEY", ""),
    "image_size": "512x512",
    "fallback_enabled": True,
}

# Режимы контента
CONTENT_MODES = {
    "family_friendly": False,
    "adult_mode": True,
}

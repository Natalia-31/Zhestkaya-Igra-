import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в окружении!")

# Базовые игровые настройки (можно менять)
GAME_SETTINGS = {
    "MIN_PLAYERS": 2,
    "HAND_SIZE": 10,
    "ROUND_TIMEOUT": 60,  # в секундах
}

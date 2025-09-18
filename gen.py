import logging
from datetime import datetime

# Настройка логирования в файл
logging.basicConfig(
    filename="game_events.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def format_error(text: str) -> str:
    return f"❌ Ошибка: {text}"

def format_info(text: str) -> str:
    return f"ℹ️ {text}"

def log_event(event_type: str, details: str) -> None:
    logging.info(f"{event_type} | {details}")

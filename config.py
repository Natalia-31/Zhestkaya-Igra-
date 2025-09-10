# Настройки игры
GAME_SETTINGS = {
    "max_players": 10,
    "cards_per_hand": 10,
    "round_timeout": 120,  # секунд
    "min_players": 2,      # минимум 2 игрока
}

# Режимы контента
CONTENT_MODES = {
    "family_friendly": False,  # Лайтовая версия
    "adult_mode": True         # Включить 18+
}

# База данных (если понадобится в будущем)
DATABASE_URL = "database/game.db"

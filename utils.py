import json
import random

def load_json_file(filepath):
    """Загрузить JSON-файл и вернуть содержимое."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(filepath, data):
    """Сохранить данные в JSON-файл."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_random_situation(situations, used=None):
    """Выбрать случайную ситуацию, исключая уже использованные (если заданы)."""
    if used:
        available = [s for s in situations if s not in used]
    else:
        available = situations

    if not available:
        return None

    return random.choice(available)

def get_random_cards(all_cards, count=10):
    """Выбрать случайные карточки-ответы для игрока."""
    return random.sample(all_cards, min(count, len(all_cards)))

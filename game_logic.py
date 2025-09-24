import logging
import random
from pathlib import Path

from game_session import GameSession
from image_generator import create_card

# Настройки
CARDS_FILE = Path(__file__).parent / "cards.json"
GENERATED_DIR = Path(__file__).parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# Загрузка всех ситуаций из JSON
import json
with open(CARDS_FILE, encoding="utf-8") as f:
    ALL_SITUATIONS = json.load(f)

log = logging.getLogger(__name__)

class GameLogic:
    def __init__(self, chat_id):
        self.session = GameSession(chat_id)

    def start_game(self):
        # Раздаём первой рукодержателю карты
        self.session.reset_round()
        host = self.session.next_host()
        log.info(f"Новый ведущий: {host['username']}")
        self.session.deal_hands(ALL_SITUATIONS)
        return host

    def receive_answer(self, user_id, card_index):
        # Сохраняем карту в answers
        hand = self.session.hands.get(user_id, [])
        if 0 <= card_index < len(hand):
            card = hand.pop(card_index)
            self.session.answers[user_id] = card
            log.info(f"Игрок {user_id} ответил карточкой {card_index}")
            return card
        return None

    def all_answers_done(self):
        return self.session.all_answers_received()

    def pick_winner(self, pick_index):
        winner = self.session.pick_winner(pick_index)
        log.info(f"Победитель: {winner['username']}")
        return winner

    def generate_and_get_card_image(self, situation: str, answer: str) -> Path:
        """
        Генерирует изображение карточки через локальный API или Pillow.
        """
        filename = f"{random.randint(0,999999)}.png"
        out_path = GENERATED_DIR / filename
        path = create_card(situation, answer, use_api=True)
        return path

# Пример использования внутри бота/сервера:
if __name__ == "__main__":
    gl = GameLogic(chat_id=123456)
    host = gl.start_game()

    # Предположим, ведущий выбрал ситуацию
    situation = "Вас на свадьбе заставляют танцевать макарену перед всеми"
    gl.session.current_situation = situation

    # Игроки дают ответы...
    gl.receive_answer(user_id=1, card_index=0)
    gl.receive_answer(user_id=2, card_index=3)

    if gl.all_answers_done():
        winner = gl.pick_winner(0)
        # Генерируем изображение победной карточки
        img_path = gl.generate_and_get_card_image(situation, winner["answer"])
        print(f"Победная карточка готова: {img_path}")

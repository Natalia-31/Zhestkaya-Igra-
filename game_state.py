import random

# Константа размера руки
HAND_SIZE = 10

# Словарь хранения игровых сессий: chat_id → GameSession
game_states: dict[int, 'GameSession'] = {}

class GameSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []             # [{'user_id':…, 'username':…}]
        self.scores: dict[int, int] = {}  # user_id → очки
        self.host_index = -1
        self.round = 0
        self.state = "waiting"
        self.answers = {}             # user_id → карта
        self.current_situation = None
        self.used_situations = []
        self.hands: dict[int, list] = {}  # user_id → [карт]
        self.used_cards = []          # Использованные карты для уникальности
        self.main_deck = []           # Основная колода карт

    def add_player(self, user_id, username):
        if user_id not in [p['user_id'] for p in self.players]:
            self.players.append({"user_id": user_id, "username": username})
            self.scores[user_id] = 0

    def next_host(self):
        self.host_index = (self.host_index + 1) % len(self.players)
        return self.players[self.host_index]

    def get_host(self):
        if self.host_index >= 0 and self.players:
            return self.players[self.host_index]
        return None

    def reset_round(self):
        self.answers = {}
        self.current_situation = None
        self.round += 1
        # Не очищаем руки, чтобы сохранить 9 карт у игроков

    def all_answers_received(self):
        # Ведущий не отвечает
        return len(self.answers) >= len(self.players) - 1

    def prepare_deck(self, all_cards: list):
        """Подготовить колоду без использованных карт"""
        self.main_deck = [card for card in all_cards if card not in self.used_cards]
        random.shuffle(self.main_deck)
        # Автоматический сброс used_cards, если карт мало
        needed = (len(self.players) - 1) * HAND_SIZE
        if len(self.main_deck) < needed:
            self.used_cards.clear()
            self.main_deck = all_cards.copy()
            random.shuffle(self.main_deck)

    def deal_initial_hands(self):
        """Общая раздача 10 карт игрокам, кроме ведущего"""
        host = self.get_host()
        host_id = host['user_id'] if host else None
        for player in self.players:
            user_id = player['user_id']
            if user_id == host_id:
                continue
            hand = []
            while len(hand) < HAND_SIZE and self.main_deck:
                hand.append(self.main_deck.pop())
            self.hands[user_id] = hand

    def refill_hands(self):
        """Добираем карты до 10 у игроков, кроме ведущего"""
        host = self.get_host()
        host_id = host['user_id'] if host else None
        for player in self.players:
            user_id = player['user_id']
            if user_id == host_id:
                continue
            current_hand = self.hands.get(user_id, [])
            while len(current_hand) < HAND_SIZE and self.main_deck:
                current_hand.append(self.main_deck.pop())
            self.hands[user_id] = current_hand

    def deal_hands(self, all_cards):
        """Вызывается для первой раздачи или добора карт"""
        if not any(self.hands.values()):
            self.prepare_deck(all_cards)
            self.deal_initial_hands()
        else:
            self.refill_hands()

    def replace_used_cards(self, used_answers):
        """Заменяет использованные карты новыми у всех игроков"""
        for user_id, card in used_answers.items():
            hand = self.hands.get(user_id, [])
            if card in hand:
                hand.remove(card)
            if card not in self.used_cards:
                self.used_cards.append(card)
            if self.main_deck:
                hand.append(self.main_deck.pop())
            self.hands[user_id] = hand

    def add_score(self, user_id, points=1):
        self.scores[user_id] = self.scores.get(user_id, 0) + points

    def get_scores(self):
        return sorted(
            self.players,
            key=lambda p: self.scores.get(p['user_id'], 0),
            reverse=True
        )

    def get_score(self, user_id):
        return self.scores.get(user_id, 0)

    def pick_winner(self, idx):
        user_ids = list(self.answers.keys())
        chosen_id = user_ids[idx]
        chosen_card = self.answers[chosen_id]
        username = next((p["username"] for p in self.players if p["user_id"] == chosen_id), str(chosen_id))
        self.add_score(chosen_id)
        return {"user_id": chosen_id, "username": username, "answer": chosen_card}

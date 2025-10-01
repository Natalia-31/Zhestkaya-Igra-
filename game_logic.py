import random
from game_state import game_states, GameSession, HAND_SIZE


class GameSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []  # [{'user_id': ..., 'username': ...}]
        self.scores = {}  # user_id → score (ДОБАВЛЕНО)
        self.host_index = -1
        self.round = 0
        self.state = "waiting"
        self.answers = {}  # user_id → card
        self.current_situation = None
        self.used_situations = []
        self.hands = {}  # user_id → [cards]
        self.used_cards = []  # Отслеживание использованных карт (ДОБАВЛЕНО)
        self.main_deck = []  # Основная колода (ДОБАВЛЕНО)

    def add_player(self, user_id, username):
        if user_id not in [p['user_id'] for p in self.players]:
            self.players.append({"user_id": user_id, "username": username})
            self.scores[user_id] = 0  # Инициализация очков (ДОБАВЛЕНО)

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
        # НЕ очищаем self.hands - сохраняем карты игроков

    def all_answers_received(self):
        # Минус ведущий: он не отвечает
        return len(self.answers) >= len(self.players) - 1

    def prepare_deck(self, all_cards):
        """Подготовка колоды с учетом использованных карт"""
        self.main_deck = [card for card in all_cards if card not in self.used_cards]
        random.shuffle(self.main_deck)
        
        # Если карт мало, сбрасываем использованные
        if len(self.main_deck) < (len(self.players) - 1) * HAND_SIZE:
            self.used_cards.clear()
            self.main_deck = all_cards.copy()
            random.shuffle(self.main_deck)

    def deal_initial_hands(self):
        """Первоначальная раздача 10 уникальных карт каждому игроку"""
        host = self.get_host()
        host_id = host['user_id'] if host else None
        
        for player in self.players:
            user_id = player['user_id']
            if user_id == host_id:
                continue
                
            # Даем 10 уникальных карт
            hand = []
            while len(hand) < HAND_SIZE and self.main_deck:
                hand.append(self.main_deck.pop())
            
            self.hands[user_id] = hand

    def refill_hands(self):
        """Добираем карты до 10 штук (не заменяем все руки)"""
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

    def replace_used_cards(self, used_answers_dict):
        """Заменяет использованные карты новыми у всех игроков"""
        for user_id, card in used_answers_dict.items():
            hand = self.hands.get(user_id, [])
            
            # Удаляем использованную карту
            if card in hand:
                hand.remove(card)
            
            # Добавляем в использованные
            if card not in self.used_cards:
                self.used_cards.append(card)
            
            # Добираем новую карту
            if self.main_deck:
                hand.append(self.main_deck.pop())
            
            self.hands[user_id] = hand

    def add_score(self, user_id, points=1):
        """Начисляет очки игроку"""
        self.scores[user_id] = self.scores.get(user_id, 0) + points

    def get_scores(self):
        """Возвращает отсортированный список игроков с очками"""
        return sorted(
            self.players,
            key=lambda p: self.scores.get(p['user_id'], 0),
            reverse=True
        )

    def get_score(self, user_id):
        """Возвращает очки конкретного игрока"""
        return self.scores.get(user_id, 0)

    def pick_winner(self, idx):
        user_ids = list(self.answers.keys())
        chosen_id = user_ids[idx]
        chosen_card = self.answers[chosen_id]
        username = next((p["username"] for p in self.players if p["user_id"] == chosen_id), str(chosen_id))
        
        # Начисляем очко победителю
        self.add_score(chosen_id)
        
        return {"user_id": chosen_id, "username": username, "answer": chosen_card}

    def deal_hands(self, all_cards):
        """Устаревший метод - заменен на prepare_deck + deal_initial_hands/refill_hands"""
        self.prepare_deck(all_cards)
        if not any(self.hands.values()):  # Если это первая раздача
            self.deal_initial_hands()
        else:  # Если добираем карты
            self.refill_hands()

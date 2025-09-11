import random

HAND_SIZE = 10

class GameSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []  # [{'user_id': ..., 'username': ...}]
        self.host_index = -1
        self.round = 0
        self.state = "waiting"
        self.answers = {}  # user_id → card
        self.current_situation = None
        self.used_situations = []
        self.hands = {}  # user_id → [cards]

    def add_player(self, user_id, username):
        if user_id not in [p['user_id'] for p in self.players]:
            self.players.append({"user_id": user_id, "username": username})

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
        self.hands = {}

    def all_answers_received(self):
        # Минус ведущий: он не отвечает
        return len(self.answers) >= len(self.players) - 1

    def deal_hands(self, all_cards):
        deck = all_cards.copy()
        random.shuffle(deck)
        for p in self.players:
            if p == self.get_host(): continue
            self.hands[p['user_id']] = [deck.pop() for _ in range(HAND_SIZE)]

    def pick_winner(self, idx):
        user_ids = list(self.answers.keys())
        chosen_id = user_ids[idx]
        chosen_card = self.answers[chosen_id]
        username = next((p["username"] for p in self.players if p["user_id"] == chosen_id), str(chosen_id))
        return {"user_id": chosen_id, "username": username, "answer": chosen_card}

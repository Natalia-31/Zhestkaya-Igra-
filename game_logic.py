class GameSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []
        self.host_index = 0
        self.round = 0
        self.state = "waiting"  # or "in_progress"
        self.answers = {}
        self.current_situation = None
        self.used_situations = []

    def add_player(self, user_id, username):
        if user_id not in [p['user_id'] for p in self.players]:
            self.players.append({"user_id": user_id, "username": username})

    def next_host(self):
        self.host_index = (self.host_index + 1) % len(self.players)
        return self.players[self.host_index]

    def get_host(self):
        return self.players[self.host_index]

    def reset_round(self):
        self.answers = {}
        self.current_situation = None
        self.round += 1

    def all_answers_received(self):
        # минус 1, потому что ведущий не отвечает
        return len(self.answers) == len(self.players) - 1

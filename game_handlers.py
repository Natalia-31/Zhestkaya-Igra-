    st["answers"].clear()
    # НЕ очищаем руки, чтобы сохранить карты игроков
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    host_id = host["user_id"]
    st["current_situation"] = decks.get_random_situation()
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {st['current_situation']}")

    # Подготовка колоды: если пустая — пересобрать, исключив сыгранные и карты в руках
    def refill_main_deck():
        full = decks.get_new_shuffled_answers_deck()
        used = set(st["used_answers"])
        in_hands = set(c for h in st["hands"].values() for c in h)
        st["main_deck"] = [c for c in full if c not in used and c not in in_hands]

    if "main_deck" not in st or not isinstance(st["main_deck"], list):
        st["main_deck"] = []
    if not st["main_deck"]:
        refill_main_deck()

    # Инициализация рук у новых игроков, у существующих сохраняем и доводим до 10
    for p in st["players"]:
        uid = p["user_id"]
        if uid == host_id:
            continue
        hand = st["hands"].get(uid, [])
        if not isinstance(hand, list):
            hand = []
        # Доводим размер до 10
        while len(hand) < 10:
            if not st["main_deck"]:
                refill_main_deck()
                if not st["main_deck"]:
                    break
            hand.append(st["main_deck"].pop())
        st["hands"][uid] = hand

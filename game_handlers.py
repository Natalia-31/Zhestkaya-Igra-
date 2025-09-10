async def _start_round_logic(bot: Bot, chat_id: int, starter_id: int):
    game = GAMES.get(chat_id)
    if not game or not game["players"]:
        return await bot.send_message(chat_id, "Сначала /new_game и /join_game", reply_markup=main_menu_kb())

    # Показываем список игроков
    players = game["players"]
    mentions = []
    for uid in players:
        member = await bot.get_chat_member(chat_id, uid)
        mentions.append(f"• {member.user.full_name}")
    await bot.send_message(
        chat_id,
        f"👥 Присоединились ({len(players)}):\n" + "\n".join(mentions)
    )

    # Назначаем ведущего
    idx = game["host_index"] % len(players)
    host_id = players[idx]
    game["host_index"] += 1
    game["answers"].clear()
    game["hands"].clear()

    # Выдаём ситуацию
    situation = get_random_situation()
    game["situation"] = situation
    host_name = (await bot.get_chat_member(chat_id, host_id)).user.full_name
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host_name}\n\n🎲 {situation}")

    # Раздаём карты игрокам в личные сообщения
    deck = ALL_CARDS.copy(); random.shuffle(deck)
    for uid in players:
        if uid == host_id:
            continue
        hand = [deck.pop() for _ in range(HAND_SIZE)]
        game["hands"][uid] = hand
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({HAND_SIZE} карт) — выберите карту-ответ:", reply_markup=kb)
        except:
            pass

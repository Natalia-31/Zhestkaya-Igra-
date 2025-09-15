# В файлах game_handlers.py и admin_handlers.py
from game_utils import decks, gen

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from game_state import game_states
from game_utils import decks, gen # Импортируем оба наших менеджера

router = Router()

# --- КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ ИГРОЙ ---

@router.message(Command("newgame"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_new_game(message: Message):
    """Начинает новую игру в чате."""
    chat_id = message.chat.id
    if chat_id in game_states and game_states[chat_id].get("is_active"):
        await message.answer("Игра в этом чате уже идет! Чтобы начать заново, завершите текущую: /endgame")
        return

    # Инициализация состояния игры
    game_states[chat_id] = {
        "is_active": True,
        "host_id": message.from_user.id,
        "host_name": message.from_user.first_name,
        "players": {},
        "main_deck": decks.get_new_shuffled_answers_deck(),
        "current_situation": None,
        "played_in_round": set(),
    }
    
    await message.answer(
        f"🎉 Новая игра началась! Ведущий: {message.from_user.first_name}.\n"
        f"Чтобы присоединиться, игроки должны написать /join"
    )

@router.message(Command("join"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_join_game(message: Message, bot: Bot):
    """Добавляет игрока в игру."""
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in game_states or not game_states[chat_id].get("is_active"):
        await message.answer("Игра в этом чате еще не началась. Попросите ведущего начать ее: /newgame")
        return

    if user.id in game_states[chat_id]["players"]:
        await message.answer(f"{user.first_name}, вы уже в игре!")
        return
        
    # Добавляем игрока
    game_states[chat_id]["players"][user.id] = {
        "name": user.first_name,
        "hand": [],
        "score": 0,
    }

    # Пытаемся написать игроку в личку
    try:
        await bot.send_message(user.id, "Вы успешно присоединились к игре! Ожидайте начала раунда.")
        await message.answer(f"Игрок {user.first_name} присоединился к игре!")
    except TelegramBadRequest:
        await message.answer(
            f"⚠️ {user.first_name}, не могу написать вам в личку. "
            f"Пожалуйста, начните диалог со мной (@{bot.id}) и попробуйте снова /join."
        )
        del game_states[chat_id]["players"][user.id] # Удаляем, т.к. не сможем отправить карты

@router.message(Command("round"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_new_round(message: Message, bot: Bot):
    """Начинает новый раунд."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in game_states or not game_states[chat_id].get("is_active"):
        return

    if user_id != game_states[chat_id]["host_id"]:
        await message.answer("Только ведущий может начинать новый раунд.")
        return

    state = game_states[chat_id]
    state["played_in_round"] = set() # Сбрасываем сыгравших в раунде
    
    # Раздача/добор карт
    for player_id, player_data in state["players"].items():
        while len(player_data["hand"]) < 10:
            if not state["main_deck"]:
                await message.answer("В колоде закончились карты ответов! Игра окончена.")
                # Тут можно добавить логику завершения игры
                return
            card = state["main_deck"].pop()
            player_data["hand"].append(card)

    # Отправка ситуации в общий чат
    situation = decks.get_random_situation()
    state["current_situation"] = situation
    await message.answer(f"‼️ ВНИМАНИЕ, СИТУАЦИЯ:\n\n`{situation}`", parse_mode="Markdown")

    # Отправка карт в личку
    for player_id, player_data in state["players"].items():
        buttons = [
            [InlineKeyboardButton(text=card, callback_data=f"play_answer_{chat_id}_{card}")]
            for card in player_data["hand"]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await bot.send_message(
                player_id,
                "Ваши карты. Выберите ответ на ситуацию:",
                reply_markup=keyboard
            )
        except TelegramBadRequest:
            # Если не можем написать игроку, просто пропускаем его
            continue

# --- ОБРАБОТЧИКИ НАЖАТИЙ НА КНОПКИ ---

@router.callback_query(F.data.startswith("play_answer_"))
async def handle_play_answer(callback: CallbackQuery, bot: Bot):
    """Обрабатывает выбор ответа игроком в личке."""
    _, chat_id_str, answer = callback.data.split("_", 2)
    chat_id = int(chat_id_str)
    user = callback.from_user

    state = game_states.get(chat_id)
    if not state or not state["is_active"] or user.id not in state["players"]:
        await callback.answer("Игра не найдена или вы не являетесь ее участником.", show_alert=True)
        return
        
    if user.id in state["played_in_round"]:
        await callback.answer("Вы уже сделали ход в этом раунде.", show_alert=True)
        return

    # Отправляем кнопку с ответом в общий чат
    button = InlineKeyboardButton(text=answer, callback_data=f"select_winner_{chat_id}_{user.id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await bot.send_message(chat_id, f"Ответ от игрока {user.first_name}:", reply_markup=keyboard)

    # Обновляем состояние
    state["players"][user.id]["hand"].remove(answer)
    state["played_in_round"].add(user.id)
    
    await callback.message.edit_text("Ваш ответ принят и отправлен в общий чат!")
    await callback.answer()


@router.callback_query(F.data.startswith("select_winner_"))
async def handle_select_winner(callback: CallbackQuery, bot: Bot):
    """Обрабатывает выбор победителя ведущим в общем чате."""
    _, chat_id_str, winner_id_str = callback.data.split("_", 2)
    chat_id = int(chat_id_str)
    winner_id = int(winner_id_str)
    host = callback.from_user
    
    state = game_states.get(chat_id)
    if not state or not state["is_active"]:
        return await callback.answer()

    if host.id != state["host_id"]:
        return await callback.answer("Только ведущий может выбирать победителя!", show_alert=True)

    if not state.get("current_situation"):
        return await callback.answer("Ошибка: не найдена текущая ситуация.", show_alert=True)

    # Получаем данные победителя и его ответ
    winning_answer = callback.message.reply_markup.inline_keyboard[0][0].text
    winner_name = state["players"][winner_id]["name"]
    state["players"][winner_id]["score"] += 1
    
    await callback.message.edit_reply_markup(reply_markup=None) # Убираем кнопки у всех ответов
    await callback.answer(f"Вы выбрали ответ от {winner_name}!")
    
    await bot.send_message(chat_id, f"🏆 Победитель раунда - {winner_name} с ответом: \"{winning_answer}\"!")

    # Генерация изображения
    await bot.send_message(chat_id, "Генерирую мем...")
    await gen.generate_and_send_image(bot, chat_id, state["current_situation"], winning_answer)

    # Добор карт игроками
    for player_id in state["players"]:
        if state["main_deck"]:
            card = state["main_deck"].pop()
            state["players"][player_id]["hand"].append(card)
            try:
                await bot.send_message(player_id, f"Вы добрали карту: `{card}`", parse_mode="Markdown")
            except TelegramBadRequest:
                continue
    
    await bot.send_message(chat_id, "Раунд окончен! Все игроки добрали по одной карте. Ведущий, можно начинать следующий раунд: /round")
    state["current_situation"] = None # Сбрасываем ситуацию

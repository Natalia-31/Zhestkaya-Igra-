from typing import Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, gen, video_gen  # Добавлен video_gen для генерации видео

router = Router()

SESSIONS: Dict[int, Dict[str, Any]] = {}


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
            [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_new_game")],
            [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_new_game")],
        ]
    )


@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer("Жесткая Игра. Используйте меню.", reply_markup=main_menu())


@router.message(Command("new_game"))
async def cmd_new_game(m: Message):
    await _create_game(m.chat.id, m.from_user.id, m.from_user.full_name)
    await m.answer("✅ Игра начата!", reply_markup=main_menu())


@router.message(Command("join_game"))
async def cmd_join_game(m: Message, bot: Bot):
    await _join_flow(m.chat.id, m.from_user.id, m.from_user.full_name, bot, feedback=m)


@router.message(Command("start_round"))
async def cmd_start_round(m: Message):
    await _start_round(m.bot, m.chat.id)


@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name)
    await cb.answer()
    try:
        await cb.message.edit_text("✅ Игра начата!", reply_markup=main_menu())
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "ui_new_game")
async def ui_join_game(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback=cb.message)
    await cb.answer()


@router.callback_query(F.data == "ui_new_game")
async def ui_start_game(cb: CallbackQuery):
    await cb.answer()
    await _start_round(cb.bot, cb.message.chat.id)


async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],  # Список игроков
        "hands": {},  # Карты у игроков
        "answers": {},  # Ответы игроков в раунде
        "host_idx": -1,  # Индекс ведущего
        "current_situation": None,  # Ситуация текущего раунда
        "main_deck": [],  # Основная колода карт
        "used_answers": [],  # Использованные карты
    }


async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer("Сначала нажмите «Начать игру».", reply_markup=main_menu())
        return

    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились! Ждите начала игры.")
        except TelegramBadRequest as e:
            await feedback.answer(f"⚠️ {user_name}, напишите боту и нажмите /start. Ошибка: {e}")
            return
        st["players"].append({"user_id": user_id, "username": user_name})

    await feedback.answer(f"В игре игроков: {len(st['players'])}", reply_markup=main_menu())


async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Для игры нужно минимум 2 игрока.", reply_markup=main_menu())
        return

    st["answers"].clear()
    st["hands"].clear()
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    st["current_situation"] = decks.get_random_situation()

    host = st["players"][st["host_idx"]]
    await bot.send_message(chat_id, f"Раунд начинается! Ведущий: {host['username']}\nСитуация:\n{st['current_situation']}")

    full_deck = decks.get_new_shuffled_deck()
    st["main_deck"] = [card for card in full_deck if card not in st["used_answers"]]

    if not st["main_deck"]:
        await bot.send_message(chat_id, "Не осталось доступных карт.", reply_markup=main_menu())
        return

    for player in st["players"]:
        if player["user_id"] == host["user_id"]:
            continue
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][player["user_id"]] = hand

    for player in st["players"]:
        if player["user_id"] == host["user_id"]:
            continue

        hand = st["hands"].get(player["user_id"], [])
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{player['user_id']}:{idx}") for idx, card in enumerate(hand)]]
        )
        try:
            await bot.send_message(
                player["user_id"],
                f"Раунд начался. Ситуация:\n{st['current_situation']}\nВыберите карту из руки:",
                reply_markup=keyboard,
            )
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"Не могу отправить сообщение игроку {player['username']}.")


@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    data = cb.data.split(":")
    chat_id, user_id, card_idx = int(data[1]), int(data[2]), int(data[3])

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    if cb.from_user.id != user_id:
        await cb.answer("Это не ваша очередь.", show_alert=True)
        return

    hand = st["hands"].get(user_id, [])
    if card_idx < 0 or card_idx >= len(hand):
        await cb.answer("Неверный выбор карты.", show_alert=True)
        return

    card = hand.pop(card_idx)
    st["answers"][user_id] = card
    st["used_answers"].append(card)

    await cb.answer(f"Вы выбрали карту: {card}")

    if len(st["answers"]) >= len(st["players"]) - 1:
        answers_list = list(st["answers"].items())
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=str(i + 1), callback_data=f"pick:{chat_id}:{i}") for i in range(len(answers_list))]
            ]
        )
        text = "\n".join(
            f"{idx + 1}. {next(player['username'] for player in st['players'] if player['user_id'] == uid)} — {ans}"
            for idx, (uid, ans) in enumerate(answers_list)
        )
        await cb.message.answer(f"Все ответы:\n{text}", reply_markup=keyboard)


@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    data = cb.data.split(":")
    chat_id, idx = int(data[1]), int(data[2])

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    if cb.from_user.id != st["players"][st["host_idx"]]["user_id"]:
        await cb.answer("Эту функцию может выполнять только ведущий.", show_alert=True)
        return

    answers_list = list(st["answers"].items())
    if idx < 0 or idx >= len(answers_list):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    winner_id, winner_answer = answers_list[idx]
    winner_name = next(player['username'] for player in st["players"] if player['user_id'] == winner_id)

    try:
        await cb.message.edit_reply_markup()
    except TelegramBadRequest:
        pass

    await cb.message.answer(f"Победитель: {winner_name}\nОтвет: {winner_answer}")

    # Отправляем иллюстрацию и видео победителя
    await gen.send_illustration(cb.bot, chat_id, st["current_situation"], winner_answer)
    await video_gen.send_video_illustration(cb.bot, chat_id, st["current_situation"], winner_answer)

    # Раздача новых карт
    for player in st["players"]:
        if player["user_id"] == st["players"][st["host_idx"]]["user_id"]:
            continue

        if not st["main_deck"]:
            full_deck = decks.get_new_shuffled_deck()
            used = st["used_answers"]
            in_hands = [card for hand in st["hands"].values() for card in hand]
            st["main_deck"] = [card for card in full_deck if card not in used and card not in in_hands]

            if not st["main_deck"]:
                await cb.message.answer("Карт для добора больше нет.")
                return

        new_card = st["main_deck"].pop()
        st["hands"].setdefault(player["user_id"], []).append(new_card)

        try:
            await cb.bot.send_message(
                player["user_id"],
                f"Вы получили новую карту: {new_card}\nВсего карт в руке: {len(st['hands'][player['user_id']])}",
            )
        except TelegramBadRequest:
            pass

    await cb.message.answer("Раунд завершён.", reply_markup=main_menu())

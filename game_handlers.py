from typing import Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, gen, video_gen  # Добавлен video_gen

router = Router()

SESSIONS: Dict[int, Dict[str, Any]] = {}


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
            [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join")],
            [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start")]
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


@router.callback_query(F.data == "ui_join")
async def ui_join(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback=cb.message)
    await cb.answer()


@router.callback_query(F.data == "ui_start")
async def ui_start(cb: CallbackQuery):
    await cb.answer()
    await _start_round(cb.bot, cb.message.chat.id)


async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],  # [{user_id, username}]
        "hands": {},  # user_id -> List[str]
        "answers": {},  # user_id -> str
        "host_idx": -1,
        "current_situation": None,
        "main_deck": [],  # ответы из answers.json
        "used_answers": []  # уже сыгранные
    }


async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback: Message):
    st = SESSIONS.get(chat_id)
    if not st:
        await feedback.answer("Сначала нажмите «Начать игру».", reply_markup=main_menu())
        return
    if user_id not in [p["user_id"] for p in st["players"]]:
        try:
            await bot.send_message(user_id, "Вы присоединились! Ожидайте начала раунда.")
        except TelegramBadRequest as e:
            await feedback.answer(f"⚠️ {user_name}, нажмите Start у бота и повторите. {e}")
            return
        st["players"].append({"user_id": user_id, "username": user_name})
    await feedback.answer(f"✅ Игроков: {len(st['players'])}", reply_markup=main_menu())


async def _start_round(bot: Bot, chat_id: int):
    st = SESSIONS.get(chat_id)
    if not st or len(st["players"]) < 2:
        await bot.send_message(chat_id, "Для игры нужны минимум 2 игрока.", reply_markup=main_menu())
        return

    print(f"🎲 Начинаем раунд, уже сыграны {len(st['used_answers'])} карт")
    st["answers"] = {}
    st["hands"] = {}
    st["host_idx"] = (st["host_idx"] + 1) % len(st["players"])
    host = st["players"][st["host_idx"]]
    st["current_situation"] = decks.get_random_situation()

    await bot.send_message(chat_id, f"Раунд! Ведущий — {host['username']}\n\nСитуация: {st['current_situation']}")

    full_deck = decks.get_new_shuffled_deck()
    st["main_deck"] = [card for card in full_deck if card not in st["used_answers"]]

    if not st["main_deck"]:
        await bot.send_message(chat_id, "Карт для добора не осталось!")
        return

    for p in st["players"]:
        if p["user_id"] == host["user_id"]:
            continue
        hand = []
        while len(hand) < 10 and st["main_deck"]:
            hand.append(st["main_deck"].pop())
        st["hands"][p["user_id"]] = hand

    for p in st["players"]:
        if p["user_id"] == host["user_id"]:
            continue
        hand = st["hands"].get(p["user_id"], [])
        buttons = [
            [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{p['user_id']}:{i}")]
            for i, card in enumerate(hand)
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await bot.send_message(p["user_id"], f"Ситуация: {st['current_situation']}\nВыберите карту:", reply_markup=keyboard)
        except TelegramBadRequest:
            await bot.send_message(chat_id,
                                   f"Не могу написать игроку {p['username']} - пишите, пожалуйста, боту напрямую.")


@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery):
    q = cb.data.split(":")
    chat_id = int(q[1])
    user_id = int(q[2])
    idx = int(q[3])

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена", show_alert=True)
        return

    if cb.from_user.id != user_id:
        await cb.answer("Вы сейчас не у себя в руке", show_alert=True)
        return

    hand = st["hands"].get(user_id, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неправильный индекс карты", show_alert=True)
        return

    card = hand.pop(idx)
    st["answers"][user_id] = card
    st["used_answers"].append(card)

    await cb.answer(f"Вы выбрали: {card}")

    if len(st["answers"]) >= len(st["players"]) - 1:
        answers = list(st["answers"].items())
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i + 1), callback_data=f"pick:{chat_id}:{i}") for i in range(len(answers))]
        ])
        text = "\n".join(
            f"{i + 1}. {next(p['username'] for p in st['players'] if p['user_id'] == uid)} — {ans}"
            for i, (uid, ans) in enumerate(answers)
        )
        await cb.message.answer(f"Ответы игроков:\n{text}", reply_markup=keyboard)


@router.callback_query(F.data.startswith("pick:"))
async def on_pick(cb: CallbackQuery):
    _, chat_id_str, idx_str = cb.data.split(":")
    chat_id = int(chat_id_str)
    idx = int(idx_str)

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена", show_alert=True)
        return

    if cb.from_user.id != st["players"][st["host_idx"]]["user_id"]:
        await cb.answer("Только ведущий может выбирать", show_alert=True)
        return

    answers = list(st["answers"].items())
    if idx < 0 or idx >= len(answers):
        await cb.answer("Неправильный индекс", show_alert=True)
        return

    winner_uid, winner_answer = answers[idx]
    winner_name = next(p["username"] for p in st["players"] if p["user_id"] == winner_uid)

    try:
        await cb.message.edit_reply_markup()
    except TelegramBadRequest:
        pass

    await cb.message.answer(f"Победитель: {winner_name}\nОтвет: {winner_answer}")

    await gen.send_illustration(cb.bot, chat_id, st["current_situation"], winner_answer)
    await video_gen.send_video_illustration(cb.bot, chat_id, st["current_situation"], winner_answer)

    # Добор карт
    for p in st["players"]:
        if p["user_id"] == st["players"][st["host_idx"]]["user_id"]:
            continue
        if not st["main_deck"]:
            full_deck = decks.get_new_shuffled_deck()
            used = st["used_answers"]
            in_hands = [card for hand in st["hands"].values() for card in hand]
            st["main_deck"] = [card for card in full_deck if card not in used and card not in in_hands]
            if not st["main_deck"]:
                await cb.message.answer("Карт для добора нет.")
                return

        new_card = st["main_deck"].pop()
        st["hands"].setdefault(p["user_id"], []).append(new_card)
        try:
            await cb.bot.send_message(
                p["user_id"],
                f"Вы добрали карту: {new_card}\nУ вас теперь {len(st['hands'][p['user_id']])} карт.",
            )
        except TelegramBadRequest:
            pass

    await cb.message.answer("Раунд завершён.", reply_markup=main_menu())

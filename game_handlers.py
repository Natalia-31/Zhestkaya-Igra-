from typing import Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from game_utils import decks, gen, video_gen  # video_gen для генерации видео

router = Router()

SESSIONS: Dict[int, Dict] = {}

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game")],
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game")],
        [InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message):
    print(f"User {m.from_user.id} started bot")
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
async def on_new_game(cb: CallbackQuery):
    print(f"'Начать игру' pressed by {cb.from_user.id}")
    await _create_game(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name)
    await cb.answer()
    try:
        await cb.message.edit_text("✅ Игра начата!", reply_markup=main_menu())
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "ui_join_game")
async def on_join_game(cb: CallbackQuery, bot: Bot):
    print(f"'Присоединиться' pressed by {cb.from_user.id}")
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback=cb.message)
    await cb.answer()

@router.callback_query(F.data == "ui_start_round")
async def on_start_round(cb: CallbackQuery):
    print(f"'Новый раунд' pressed by {cb.from_user.id}")
    await cb.answer()
    await _start_round(cb.bot, cb.message.chat.id)

async def _create_game(chat_id: int, host_id: int, host_name: str):
    SESSIONS[chat_id] = {
        "players": [],
        "hands": {},
        "answers": {},
        "host_idx": -1,
        "current_situation": None,
        "main_deck": [],
        "used_answers": []
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

    await bot.send_message(chat_id, f"Раунд начинается! Ведущий: {host['username']}\n\nСитуация:\n{st['current_situation']}")

    full_deck = decks.get_new_shuffled_answers_deck()
    st["main_deck"] = [card for card in full_deck if card not in st["used_answers"]]

    if not st["main_deck"]:
        await bot.send_message(chat_id, "Карт для добора больше нет.", reply_markup=main_menu())
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
            [InlineKeyboardButton(text=card, callback_data=f"ans:{chat_id}:{p['user_id']}:{idx}") for idx, card in enumerate(hand)]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await bot.send_message(
                p["user_id"],
                f"Раунд начался. Ситуация:\n{st['current_situation']}\nВыберите карту из руки:",
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            await bot.send_message(chat_id, f"⚠️ Не могу написать игроку {p['username']}. Ошибка: {e}")

@router.callback_query(F.data.startswith("ans:"))
async def handle_answer(cb: CallbackQuery):
    data = cb.data.split(":")
    chat_id, user_id, card_idx = int(data[1]), int(data[2]), int(data[3])

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return
    if cb.from_user.id != user_id:
        await cb.answer("Сейчас не ваша очередь.", show_alert=True)
        return

    hand = st["hands"].get(user_id, [])
    if card_idx < 0 or card_idx >= len(hand):
        await cb.answer("Неверный выбор карты.", show_alert=True)
        return

    card = hand.pop(card_idx)
    st["answers"][user_id] = card
    st["used_answers"].append(card)

    await cb.answer(f"Вы выбрали карту: {card}")

    if len(st["answers"]) == len(st["players"]) - 1:
        answers_list = list(st["answers"].items())
        buttons = [
            [InlineKeyboardButton(text=str(i + 1), callback_data=f"pick:{chat_id}:{i}") for i in range(len(answers_list))]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "\n".join(
            f"{i+1}. {next(p['username'] for p in st['players'] if p['user_id'] == uid)} — {ans}"
            for i, (uid, ans) in enumerate(answers_list)
        )
        await cb.message.answer(f"Ответы игроков:\n{text}", reply_markup=keyboard)

@router.callback_query(F.data.startswith("pick:"))
async def handle_pick(cb: CallbackQuery):
    data = cb.data.split(":")
    chat_id, idx = int(data[1]), int(data[2])

    st = SESSIONS.get(chat_id)
    if not st:
        await cb.answer("Игра не найдена.", show_alert=True)
        return
    if cb.from_user.id != st['players'][st['host_idx']]['user_id']:
        await cb.answer("Только ведущий может выбирать.", show_alert=True)
        return

    answers_list = list(st["answers"].items())
    if idx < 0 or idx >= len(answers_list):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    winner_id, winner_answer = answers_list[idx]
    winner_name = next(p['username'] for p in st['players'] if p['user_id'] == winner_id)

    try:
        await cb.message.edit_reply_markup()
    except TelegramBadRequest:
        pass

    await cb.message.answer(f"Победитель: {winner_name}\nОтвет: {winner_answer}")

    # Генерация иллюстрации и видео победителя
    await gen.send_illustration(cb.bot, chat_id, st['current_situation'], winner_answer)
    await video_gen.send_video_illustration(cb.bot, chat_id, st['current_situation'], winner_answer)

    # Добор карт после раунда
    for p in st['players']:
        if p['user_id'] == st['players'][st['host_idx']]['user_id']:
            continue
        if not st['main_deck']:
            full_deck = decks.get_new_shuffled_deck()
            used = st['used_answers']
            in_hand = [card for hand in st['hands'].values() for card in hand]
            st['main_deck'] = [c for c in full_deck if c not in used and c not in in_hand]
            if not st['main_deck']:
                await cb.message.answer("Карт для добора больше нет.")
                return
        new_card = st['main_deck'].pop()
        st['hands'].setdefault(p['user_id'], []).append(new_card)
        try:
            await cb.bot.send_message(
                p['user_id'],
                f"Вы получили новую карту: {new_card}\nКарт у вас теперь: {len(st['hands'][p['user_id']])}"
            )
        except TelegramBadRequest:
            pass

    await cb.message.answer("Раунд завершён.", reply_markup=main_menu())

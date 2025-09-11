from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import json, random
from game_utils import gen, get_random_situation
from game_logic import GameSession

router = Router()
with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)

SESSIONS = {}  # chat_id → GameSession

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Начать игру", callback_data="new_game"),
        InlineKeyboardButton(text="➕ Присоединиться", callback_data="join_game"),
        InlineKeyboardButton(text="🎲 Новый раунд", callback_data="start_round"),
    ]])

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🎮 Жесткая Игра\n\n"
        "/new_game — начать игру\n"
        "/join_game — присоединиться к игре\n"
        "/start_round — запустить новый раунд",
        reply_markup=main_menu_kb()
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    session = GameSession(message.chat.id)
    SESSIONS[message.chat.id] = session
    await message.answer("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())

@router.callback_query(F.data == "new_game")
async def cb_new_game(callback: CallbackQuery):
    session = GameSession(callback.message.chat.id)
    SESSIONS[callback.message.chat.id] = session
    await callback.answer("Игра начата!")
    try:
        await callback.message.edit_text("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())
    except TelegramBadRequest:
        pass

@router.message(Command("join_game"))
async def cmd_join_game(message: Message):
    session = SESSIONS.get(message.chat.id)
    if not session:
        return await message.answer("Сначала /new_game", reply_markup=main_menu_kb())
    session.add_player(message.from_user.id, message.from_user.full_name)
    count = len(session.players)
    await message.answer(f"➕ {message.from_user.full_name} присоединился! Сейчас игроков: {count}", reply_markup=main_menu_kb())

@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery):
    session = SESSIONS.get(callback.message.chat.id)
    if not session:
        return await callback.answer("Сначала /new_game", show_alert=True)
    session.add_player(callback.from_user.id, callback.from_user.full_name)
    count = len(session.players)
    await callback.answer(f"{callback.from_user.full_name} присоединился! Всего игроков: {count}")
    try:
        await callback.message.edit_text(f"✅ Игра начата! Пока игроков: {count}", reply_markup=main_menu_kb())
    except TelegramBadRequest:
        pass

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    await _start_round_logic(message.bot, message.chat.id)

@router.callback_query(F.data == "start_round")
async def cb_start_round(callback: CallbackQuery):
    await callback.answer()
    await _start_round_logic(callback.bot, callback.message.chat.id)

async def _start_round_logic(bot: Bot, chat_id: int):
    session = SESSIONS.get(chat_id)
    if not session or len(session.players) < 1:
        return await bot.send_message(chat_id, "Нужно минимум 1 игрока: /join_game", reply_markup=main_menu_kb())

    # Показываем список игроков
    mentions = [f"• {p['username']}" for p in session.players]
    await bot.send_message(chat_id, f"👥 Присоединились ({len(mentions)}):\n" + "\n".join(mentions))

    host = session.next_host()
    session.reset_round()
    situation = session.current_situation = get_random_situation()
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {situation}")

    # Раздаём карты
    session.deal_hands(ALL_CARDS)
    for uid, hand in session.hands.items():
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({len(hand)} карт) — выберите карту-ответ:", reply_markup=kb)
        except:
            pass

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    session = SESSIONS.get(chat_id)
    uid = callback.from_user.id
    host_id = session.get_host()['user_id']

    if uid == host_id:
        return await callback.answer("Ведущий не отвечает.", show_alert=True)

    idx = int(callback.data.split(":", 1)[1])
    hand = session.hands.get(uid, [])
    if idx < 0 or idx >= len(hand):
        return await callback.answer("Неверный выбор.", show_alert=True)
    card = hand.pop(idx)
    session.answers[uid] = card
    await callback.answer(f"Вы выбрали: {card}")

    if session.all_answers_received():
        answers = [session.answers[uid] for uid in session.answers]
        player_names = [next(p['username'] for p in session.players if p['user_id'] == uid) for uid in session.answers]
        text = "Ответы игроков:\n" + "\n".join(f"{i+1}. {player_names[i]} — {ans}" for i, ans in enumerate(answers))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"pick:{i}")]
            for i in range(len(answers))
        ])
        await callback.bot.send_message(chat_id, text, reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    session = SESSIONS.get(chat_id)
    host_id = session.get_host()['user_id']
    if callback.from_user.id != host_id:
        return await callback.answer("Только ведущий может выбирать.", show_alert=True)
    idx = int(callback.data.split(":", 1)[1])
    winner_info = session.pick_winner(idx)
    await callback.message.edit_text(f"🏆 Победитель: {winner_info['username']}\nОтвет: {winner_info['answer']}")

    await gen.generate_and_send_image(callback.bot, chat_id, session.current_situation, winner_info["answer"])
    await callback.bot.send_message(chat_id, "Используйте меню для нового раунда:", reply_markup=main_menu_kb())

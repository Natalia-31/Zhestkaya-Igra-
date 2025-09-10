from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
import json
import random
from game_utils import generate_image_from_situation

router = Router()

HAND_SIZE = 10

# Хранилище состояния игр: chat_id → состояние
GAMES = {}  # { chat_id: { players: [ids], host_index: int, situation: str, hands: {user_id: [cards]}, answers: [(user_id, card)] } }

# Загрузка всех карточек
with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton("▶️ Начать игру", callback_data="new_game"),
        InlineKeyboardButton("➕ Присоединиться", callback_data="join_game"),
        InlineKeyboardButton("🎲 Новый раунд", callback_data="start_round"),
    ]])


@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = {
        "players": [],
        "host_index": 0,
        "situation": None,
        "hands": {},
        "answers": []
    }
    await message.answer(
        "✅ Игра начата! Игроки, присоединяйтесь.",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "new_game")
async def cb_new_game(callback: CallbackQuery):
    GAMES[callback.message.chat.id] = {
        "players": [],
        "host_index": 0,
        "situation": None,
        "hands": {},
        "answers": []
    }
    await callback.answer("Игра начата!", show_alert=False)


@router.message(Command("join_game"))
async def cmd_join_game(message: Message):
    game = GAMES.get(message.chat.id)
    if not game:
        return await message.answer("Сначала начните игру: /new_game")
    uid = message.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await message.answer(
        f"➕ {message.from_user.full_name} присоединился!",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery):
    game = GAMES.get(callback.message.chat.id)
    if not game:
        return await callback.answer("Сначала начните игру.", show_alert=True)
    uid = callback.from_user.id
    if uid not in game["players"]:
        game["players"].append(uid)
    await callback.answer(f"{callback.from_user.full_name} присоединился!", show_alert=False)


@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    await _start_round_logic(message.bot, message.chat.id, message.from_user.id)

@router.callback_query(F.data == "start_round")
async def cb_start_round(callback: CallbackQuery):
    await callback.answer()
    await _start_round_logic(callback.bot, callback.message.chat.id, callback.from_user.id)


async def _start_round_logic(bot: Bot, chat_id: int, starter_id: int):
    game = GAMES.get(chat_id)
    if not game or not game["players"]:
        return await bot.send_message(chat_id, "Сначала /new_game и /join_game")
    # Назначаем ведущего по кругу
    host_index = game["host_index"] % len(game["players"])
    host_id = game["players"][host_index]
    game["host_index"] = host_index + 1
    game["answers"].clear()
    game["hands"].clear()
    # Выбираем ситуацию
    sit = get_random_situation()
    game["situation"] = sit
    # Объявляем в чат
    host_name = (await bot.get_chat_member(chat_id, host_id)).user.full_name
    await bot.send_message(
        chat_id,
        f"🎬 Раунд! 👑 Ведущий: {host_name}\n\n🎲 Ситуация: {sit}"
    )
    # Раздаём карты
    deck = ALL_CARDS.copy()
    random.shuffle(deck)
    for uid in game["players"]:
        if uid == host_id:
            continue
        hand = [deck.pop() for _ in range(HAND_SIZE)]
        game["hands"][uid] = hand
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{i}")] 
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, "Ваша рука — выберите ответ:", reply_markup=kb)
        except:
            pass  # игрок возможно не в личке

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    uid = callback.from_user.id
    game = GAMES.get(chat_id)
    if not game or uid == game["players"][(game["host_index"]-1) % len(game["players"])]:
        return await callback.answer("Вы не можете отвечать.", True)
    idx = int(callback.data.split(":",1)[1])
    hand = game["hands"].get(uid, [])
    if idx<0 or idx>=len(hand):
        return await callback.answer("Неверно.", True)
    card = hand.pop(idx)
    game["answers"].append((uid, card))
    await callback.answer(f"Вы выбрали: {card}")
    # Когда все ответили
    expected = len(game["players"]) -1
    if len(game["answers"])>=expected:
        # Показать ответы в чат
        text = "Ответы:\n" + "\n".join(f"{i+1}. {c}" for i,(__,c) in enumerate(game["answers"]))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"pick:{i}")] 
            for i in range(len(game["answers"]))
        ])
        await bot.send_message(chat_id, text, reply_markup=kb)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = GAMES.get(chat_id)
    host_id = game["players"][(game["host_index"]-1) % len(game["players"])]
    if callback.from_user.id != host_id:
        return await callback.answer("Только ведущий.", True)
    idx = int(callback.data.split(":",1)[1])
    uid, card = game["answers"][idx]
    winner_name = (await callback.bot.get_chat_member(chat_id, uid)).user.full_name
    await callback.message.edit_text(f"🏆 Победитель: {winner_name}\nОтвет: {card}")
    # Генерируем изображение на основе ситуации+ответ
    image_path = await generate_image_from_situation(f"{game['situation']} ____ {card}", f"round_{chat_id}")
    if image_path:
        await callback.bot.send_photo(chat_id, photo=InlineKeyboardButton(""), # placeholder
                                      caption=f"Иллюстрация к ответу '{card}'")
    # Очистка для следующего раунда
    game["situation"]=None
    game["hands"].clear()
    game["answers"].clear()
    await callback.bot.send_message(chat_id, "Нажмите «Новый раунд» или /start_round", reply_markup=main_menu_kb())

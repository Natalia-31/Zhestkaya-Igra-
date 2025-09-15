# handlers/game_handlers.py — объединённая логика меню + рабочий игровой поток

from typing import Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
import json

# Колоды/генерация — только из game_utils (без циклов)
from game_utils import decks, gen
# Твоя игровая сессия (логика раздачи/очередности/подсчёта)
from game_logic import GameSession

router = Router()

# ---------------- ДАННЫЕ ----------------

# Загружаем карты для раздачи (как в рабочем коде)
with open("cards.json", "r", encoding="utf-8") as f:
    ALL_CARDS = json.load(f)

# Хранилище сессий по групповому чату
SESSIONS: Dict[int, GameSession] = {}

# ---------------- КНОПКИ МЕНЮ ----------------

def main_menu_kb(is_host: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="▶️ Начать игру", callback_data="ui_new_game"),
            InlineKeyboardButton(text="➕ Присоединиться", callback_data="ui_join_game"),
        ],
        [
            InlineKeyboardButton(text="🎲 Новый раунд", callback_data="ui_start_round")
        ]
    ]
    # Можно скрывать кнопку “Новый раунд” не-хостам при желании,
    # но для простоты оставим общий видимым и проверим право при нажатии.
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ---------------- СТАРТ ----------------

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🎮 Жесткая Игра\n\n"
        "/new_game — начать игру\n"
        "/join_game — присоединиться к игре\n"
        "/start_round — запустить новый раунд",
        reply_markup=main_menu_kb()
    )

# ---------------- КОМАНДЫ (дублируют кнопки) ----------------

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    await _create_game(message.chat.id, host_id=message.from_user.id, host_name=message.from_user.full_name)
    await message.answer("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())

@router.message(Command("join_game"))
async def cmd_join_game(message: Message, bot: Bot):
    await _join_flow(message.chat.id, message.from_user.id, message.from_user.full_name, bot, feedback_message=message)

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    await _start_round_logic(message.bot, message.chat.id)

# ---------------- ИНЛАЙН-КНОПКИ МЕНЮ ----------------

@router.callback_query(F.data == "ui_new_game")
async def ui_new_game(cb: CallbackQuery):
    await _create_game(cb.message.chat.id, host_id=cb.from_user.id, host_name=cb.from_user.full_name)
    await cb.answer()
    try:
        await cb.message.edit_text("✅ Игра начата! Пока игроков: 0", reply_markup=main_menu_kb())
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "ui_join_game")
async def ui_join_game(cb: CallbackQuery, bot: Bot):
    await _join_flow(cb.message.chat.id, cb.from_user.id, cb.from_user.full_name, bot, feedback_message=cb.message)
    await cb.answer()

@router.callback_query(F.data == "ui_start_round")
async def ui_start_round(cb: CallbackQuery):
    await cb.answer()
    await _start_round_logic(cb.bot, cb.message.chat.id)

# ---------------- ЯДРО: СОЗДАНИЕ, ПРИСОЕДИНЕНИЕ, РАУНД ----------------

async def _create_game(chat_id: int, host_id: int, host_name: str):
    # Если игра уже была — перезаписываем (как в твоей логике)
    session = GameSession(chat_id)
    # Зафиксируем хоста в сессии, если класс поддерживает или добавим поле
    # В твоём GameSession есть метод next_host(); используем его для выбора.
    # Дополнительно можно хранить текущего хоста внутри session.
    SESSIONS[chat_id] = session
    # Можно вывести инфо:
    # print(f"New game in chat {chat_id}, host {host_name} ({host_id})")

async def _join_flow(chat_id: int, user_id: int, user_name: str, bot: Bot, feedback_message: Message):
    session = SESSIONS.get(chat_id)
    if not session:
        await feedback_message.answer("Сначала нажмите “Начать игру” или /new_game", reply_markup=main_menu_kb())
        return

    # Пытаемся написать в личку, чтобы потом раздавать карты
    try:
        await bot.send_message(user_id, "Вы присоединились к игре! Ожидайте начала раунда.")
    except TelegramBadRequest as e:
        await feedback_message.answer(
            f"⚠️ {user_name}, нажмите Start в личке у бота, затем снова “Присоединиться”.\n{e}"
        )
        return

    session.add_player(user_id, user_name)
    count = len(session.players)
    await feedback_message.answer(f"➕ {user_name} присоединился! Сейчас игроков: {count}", reply_markup=main_menu_kb())

async def _start_round_logic(bot: Bot, chat_id: int):
    session = SESSIONS.get(chat_id)
    if not session or len(session.players) < 2:
        await bot.send_message(chat_id, "Нужно минимум 2 игрока: /join_game", reply_markup=main_menu_kb())
        return

    # Список игроков
    mentions = [f"• {p['username']}" for p in session.players]
    await bot.send_message(chat_id, f"👥 Присоединились ({len(mentions)}):\n" + "\n".join(mentions))

    # Ведущий и новая ситуация
    host = session.next_host()  # как у тебя в рабочем коде
    session.reset_round()
    situation = session.current_situation = decks.get_random_situation()
    await bot.send_message(chat_id, f"🎬 Раунд! 👑 Ведущий: {host['username']}\n\n🎲 {situation}")

    # Раздача карт (как в твоей версии — из cards.json)
    session.deal_hands(ALL_CARDS)

    # Отправляем каждому игроку его руку в личку кнопками (ans:<index>)
    for uid, hand in session.hands.items():
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=card, callback_data=f"ans:{i}")]
            for i, card in enumerate(hand)
        ])
        try:
            await bot.send_message(uid, f"🎴 Ваша рука ({len(hand)} карт) — выберите карту-ответ:", reply_markup=kb)
        except TelegramBadRequest as e:
            # Покажем в общий чат, чтобы игрок знал, что надо нажать Start
            await bot.send_message(chat_id, f"⚠️ Не могу написать {uid} в личку. Нажмите Start у бота. {e}")

# ---------------- ОТВЕТ ИГРОКА: ans:<i> ----------------

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    session = SESSIONS.get(chat_id)
    if not session:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    uid = cb.from_user.id
    host_id = session.get_host()['user_id']
    if uid == host_id:
        await cb.answer("Ведущий не отвечает.", show_alert=True)
        return

    # Индекс карты в текущей руке
    try:
        idx = int(cb.data.split(":", 1)[7])
    except Exception:
        await cb.answer("Неверные данные кнопки.", show_alert=True)
        return

    hand = session.hands.get(uid, [])
    if idx < 0 or idx >= len(hand):
        await cb.answer("Неверный выбор.", show_alert=True)
        return

    card = hand.pop(idx)
    session.answers[uid] = card
    await cb.answer(f"Вы выбрали: {card}")

    # Если все сдали ответы — публикуем список и даем ведущему кнопки выбора
    if session.all_answers_received():
        answers = [session.answers[uid] for uid in session.answers]
        player_names = [next(p['username'] for p in session.players if p['user_id'] == uid) for uid in session.answers]

        text = "Ответы игроков:\n" + "\n".join(f"{i+1}. {player_names[i]} — {ans}" for i, ans in enumerate(answers))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=str(i+1), callback_data=f"pick:{i}")]
            for i in range(len(answers))
        ])
        await cb.bot.send_message(chat_id, text, reply_markup=kb)

# ---------------- ВЫБОР ПОБЕДИТЕЛЯ: pick:<i> ----------------

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    session = SESSIONS.get(chat_id)
    if not session:
        await cb.answer("Игра не найдена.", show_alert=True)
        return

    host_id = session.get_host()['user_id']
    if cb.from_user.id != host_id:
        await cb.answer("Только ведущий может выбирать.", show_alert=True)
        return

    try:
        idx = int(cb.data.split(":", 1)[7])
    except Exception:
        await cb.answer("Неверные данные.", show_alert=True)
        return

    winner_info = session.pick_winner(idx)  # должен вернуть {'user_id', 'username', 'answer'}
    # Сообщаем в чат
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await cb.message.edit_text(f"🏆 Победитель: {winner_info['username']}\nОтвет: {winner_info['answer']}")

    # Генерация изображения по ситуации и победившему ответу (через game_utils.gen)
    await gen.send_illustration(cb.bot, chat_id, session.current_situation, winner_info["answer"])

    # Добор по 1 карте в личку для всех игроков
    for pid, hand in session.hands.items():
        # Обеспечиваем достаточную колоду
        if not ALL_CARDS:
            continue
        # Здесь логика добора у тебя может быть внутри GameSession; если нет — просто выдадим новую случайную
        # Для консистентности можно хранить общий пул; оставим в простом виде:
        # new_card = random.choice(ALL_CARDS) — но лучше, чтобы не повторялась: возьми из собственного менеджера в сессии.
        # Предположим, у GameSession есть метод draw_one(); если нет — добавь.
        try:
            new_card = session.draw_one(ALL_CARDS)  # реализуй в GameSession, чтобы карточки не дублировались
        except AttributeError:
            # fallback: уникальный добор из списка, если осталось
            remaining = [c for c in ALL_CARDS if c not in hand]
            new_card = remaining if remaining else None

        if new_card:
            hand.append(new_card)
            try:
                await cb.bot.send_message(pid, f"Вы добрали карту: `{new_card}`", parse_mode="Markdown")
            except TelegramBadRequest:
                pass

    await cb.bot.send_message(chat_id, "Раунд завершён. Нажмите “🎲 Новый раунд”, чтобы продолжить.", reply_markup=main_menu_kb())

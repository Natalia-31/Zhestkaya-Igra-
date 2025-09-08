from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# Генерация простой картинки для «ситуация + ответ»
from PIL import Image, ImageDraw, ImageFont


# =====================  НАСТРОЙКИ  =====================

MIN_PLAYERS = 3
HAND_SIZE = 10
ROUND_TIMEOUT = 120  # сек. на сбор ответов

ASSETS_DIR = Path(".")
SITUATIONS_PATH = ASSETS_DIR / "situations.json"   # {"situations":[...]}
CARDS_PATH = ASSETS_DIR / "cards.json"             # {"cards":[...]}


# =====================  РОУТЕР  =====================

router = Router()


# =====================  МОДЕЛИ  =====================

@dataclass
class Answer:
    user_id: int
    text: str


@dataclass
class GameState:
    chat_id: int
    players: List[int] = field(default_factory=list)
    host_index: int = 0
    phase: str = "lobby"  # lobby | collect | choose | result
    round_no: int = 0
    current_situation: Optional[str] = None
    answers: List[Answer] = field(default_factory=list)
    hands: Dict[int, List[str]] = field(default_factory=dict)  # user_id -> hand
    deck: List[str] = field(default_factory=list)

    def current_host(self) -> Optional[int]:
        if not self.players:
            return None
        return self.players[self.host_index % len(self.players)]

    def next_host(self):
        if self.players:
            self.host_index = (self.host_index + 1) % len(self.players)


# =====================  ГЛОБАЛЬНОЕ СОСТОЯНИЕ  =====================

GAMES: Dict[int, GameState] = {}  # chat_id -> GameState
ALL_SITUATIONS: List[str] = []
ALL_CARDS: List[str] = []


# =====================  ЗАГРУЗКА КОНТЕНТА  =====================

def load_situations_cards():
    """Подгрузить ситуации и карты из файлов, если они есть; иначе — дефолт."""
    global ALL_SITUATIONS, ALL_CARDS

    # Ситуации
    if SITUATIONS_PATH.exists():
        try:
            data = json.loads(SITUATIONS_PATH.read_text(encoding="utf-8"))
            ALL_SITUATIONS = list(data.get("situations", []))
        except Exception:
            ALL_SITUATIONS = []
    if not ALL_SITUATIONS:
        ALL_SITUATIONS = [
            "Утро понедельника. Ты заходишь в офис и видишь только...",
            "В пустыне внезапно появляется табличка с надписью...",
            "Ты просыпаешься в незнакомом месте, но рядом лежит...",
            "Ведущий объявляет: «Тема дня — ...»",
        ]

    # Карты-ответы
    if CARDS_PATH.exists():
        try:
            data = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
            ALL_CARDS = list(data.get("cards", []))
        except Exception:
            ALL_CARDS = []
    if not ALL_CARDS:
        ALL_CARDS = [
            "кофе из автомата",
            "кот в коробке",
            "молчащий чат",
            "случайный уволенный",
            "яркое солнце в глаза",
            "стикеры без контекста",
            "чья-то неловкая шутка",
            "идеально пустой календарь",
            "вечная загрузка",
            "пицца без ананасов",
            "магия Ctrl+Z",
        ]


# =====================  УТИЛИТЫ  =====================

def ensure_game(chat_id: int) -> GameState:
    game = GAMES.get(chat_id)
    if not game:
        game = GameState(chat_id=chat_id)
        GAMES[chat_id] = game
    return game


def deal_to_full_hand(game: GameState, user_id: int):
    """Добрать карты игроку до HAND_SIZE из колоды; если колода пуста — перетасовать."""
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE:
        if not game.deck:
            game.deck = ALL_CARDS.copy()
            random.shuffle(game.deck)
        hand.append(game.deck.pop())


def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for idx, card in enumerate(hand):
        title = card if len(card) <= 35 else card[:32] + "…"
        rows.append([InlineKeyboardButton(text=f"👉 {title}", callback_data=f"ans:{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    rows = []
    for idx, _ in enumerate(answers, 1):
        rows.append([InlineKeyboardButton(text=f"Выбрать #{idx}", callback_data=f"pick:{idx-1}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def answers_summary(answers: List[Answer]) -> str:
    if not answers:
        return "Ответов пока нет."
    lines = [f"#{i+1}: {a.text}" for i, a in enumerate(answers)]
    return "Ответы игроков:\n\n" + "\n".join(lines)


async def generate_image_file(situation: str, answer: str, out_path: Path) -> Path:
    """Сгенерировать PNG-картинку 1024x1024 с текстом (без внешних API)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1024, 1024), color=(245, 246, 248))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 42)
        font_body = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.text((40, 40), "Жесткая Игра", fill=(20, 20, 20), font=font_title)

    def wrap(text: str, width: int = 28) -> List[str]:
        words = text.split()
        lines, buf = [], []
        for w in words:
            buf.append(w)
            if len(" ".join(buf)) > width:
                lines.append(" ".join(buf))
                buf = []
        if buf:
            lines.append(" ".join(buf))
        return lines

    y = 120
    draw.text((40, y), "Ситуация:", fill=(40, 40, 40), font=font_body)
    y += 40
    for line in wrap(situation, 30):
        draw.text((60, y), line, fill=(10, 10, 10), font=font_body)
        y += 36

    y += 20
    draw.text((40, y), "Ответ:", fill=(40, 40, 40), font=font_body)
    y += 40
    for line in wrap(answer, 30):
        draw.text((60, y), line, fill=(10, 10, 10), font=font_body)
        y += 36

    img.save(out_path)
    return out_path


async def show_answers_for_all_message(message: Message):
    chat_id = message.chat.id
    game = ensure_game(chat_id)
    if not game.answers:
        await message.answer("Ответов пока нет.")
        return
    random.shuffle(game.answers)
    game.phase = "choose"

    text = (
        f"🧾 Ситуация:\n<b>{game.current_situation}</b>\n\n"
        + answers_summary(game.answers)
        + "\n\nВедущий выбирает лучший ответ."
    )
    kb = make_choices_keyboard(game.answers)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def show_answers_for_all_by_chat(chat_id: int):
    game = ensure_game(chat_id)
    if not game.answers:
        await router.bot.send_message(chat_id, "Ответов нет — показывать нечего.")
        return
    random.shuffle(game.answers)
    game.phase = "choose"

    text = (
        f"🧾 Ситуация:\n<b>{game.current_situation}</b>\n\n"
        + answers_summary(game.answers)
        + "\n\nВедущий выбирает лучший ответ."
    )
    kb = make_choices_keyboard(game.answers)
    await router.bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


# =====================  ХЕНДЛЕРЫ  =====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Создать новую игру", callback_data="start_new")],
        [InlineKeyboardButton(text="➕ Присоединиться (в группе — /join)", callback_data="noop")],
    ])
    await message.answer(
        "Привет! Это «Жесткая Игра» — аналог 500 Злобных карт в Telegram.\n\n"
        "Как играть в группе:\n"
        "• /new_game — создать лобби\n"
        "• /join — присоединиться\n"
        "• /start_round — начать раунд\n"
        "• /answer — выбрать карточку-ответ\n"
        "• Ведущий видит ответы всех и выбирает лучший — бот шлёт картинку.\n",
        reply_markup=kb
    )


@router.callback_query(F.data == "start_new")
async def cb_start_new(call: CallbackQuery):
    await call.message.answer("Ок! Создаю игру… В группе нажмите /new_game и зовите игроков.")
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer("В группе просто отправь команду /join", show_alert=False)


@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    game = ensure_game(message.chat.id)

    # Сброс состояния
    game.players.clear()
    game.hands.clear()
    game.deck = ALL_CARDS.copy()
    random.shuffle(game.deck)
    game.phase = "lobby"
    game.round_no = 0
    game.host_index = 0
    game.current_situation = None
    game.answers.clear()

    await message.answer(
        "🃏 Игра создана!\n\n"
        "Жмите /join чтобы присоединиться. Минимум игроков: 3.\n"
        "Когда все соберутся — /start_round."
    )


@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    if message.from_user is None:
        return

    uid = message.from_user.id
    if uid in game.players:
        await message.reply("Ты уже в игре! ✋")
        return

    game.players.append(uid)
    deal_to_full_hand(game, uid)

    await message.answer(
        f"✅ {message.from_user.full_name} присоединился.\n"
        f"Игроков сейчас: {len(game.players)}"
    )


@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        await message.answer(f"Нужно минимум {MIN_PLAYERS} игрока(ов), сейчас {len(game.players)}.")
        return

    # Старт нового раунда
    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()
    host_id = game.current_host()
    game.current_situation = random.choice(ALL_SITUATIONS)

    await message.answer(
        f"🎬 Раунд #{game.round_no}\n"
        f"Ведущий: <a href=\"tg://user?id={host_id}\">{host_id}</a>\n\n"
        f"Ситуация:\n<b>{game.current_situation}</b>\n\n"
        f"Игроки, присылайте ответы — команда /answer",
        parse_mode="HTML"
    )

    # Таймаут на сбор ответов
    asyncio.create_task(round_timeout_watchdog(message.chat.id, ROUND_TIMEOUT))


@router.message(Command("answer"))
async def cmd_answer(message: Message):
    """Показать игроку его руку и дать выбрать карту-ответ."""
    game = ensure_game(message.chat.id)
    if message.from_user is None:
        return
    uid = message.from_user.id

    if game.phase != "collect":
        await message.reply("Сейчас нельзя отвечать.")
        return
    if uid not in game.players:
        await message.reply("Ты ещё не присоединился. Жми /join")
        return
    if any(a.user_id == uid for a in game.answers):
        await message.reply("Ты уже отправил ответ в этом раунде.")
        return

    hand = game.hands.get(uid, [])
    if not hand:
        deal_to_full_hand(game, uid)
        hand = game.hands[uid]

    kb = make_answers_keyboard(hand)
    await message.reply("Выбери карточку-ответ:", reply_markup=kb)


@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery):
    """Игрок выбрал карту-ответ из своей руки."""
    if not callback.message or callback.from_user is None:
        return
    game = ensure_game(callback.message.chat.id)

    if game.phase != "collect":
        await callback.answer("Сейчас нельзя отвечать.", show_alert=True)
        return

    uid = callback.from_user.id
    if uid not in game.players:
        await callback.answer("Ты не в игре.", show_alert=True)
        return
    if any(a.user_id == uid for a in game.answers):
        await callback.answer("Ответ уже отправлен.", show_alert=True)
        return

    try:
        idx = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    hand = game.hands.get(uid, [])
    if idx < 0 or idx >= len(hand):
        await callback.answer("Нет такой карты.", show_alert=True)
        return

    card_text = hand.pop(idx)
    game.answers.append(Answer(user_id=uid, text=card_text))
    deal_to_full_hand(game, uid)

    await callback.answer("Ответ отправлен!")
    await callback.message.edit_reply_markup(reply_markup=None)

    # Если все (кроме ведущего) ответили — показываем список
    host_id = game.current_host()
    expecting = len([p for p in game.players if p != host_id])
    if len(game.answers) >= expecting:
        await show_answers_for_all_message(callback.message)


@router.message(Command("show_answers"))
async def cmd_show_answers(message: Message):
    """Ведущий может вручную раскрыть ответы, если не все успели."""
    game = ensure_game(message.chat.id)
    if game.phase != "collect":
        await message.reply("Сейчас нельзя показывать ответы.")
        return
    await show_answers_for_all_message(message)


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery):
    """Ведущий выбирает лучший ответ."""
    if not callback.message:
        return
    game = ensure_game(callback.message.chat.id)
    if not game or game.phase != "choose":
        await callback.answer("Сейчас нельзя выбирать.", show_alert=True)
        return

    host_id = game.current_host()
    if callback.from_user is None or callback.from_user.id != host_id:
        await callback.answer("Выбирать может только ведущий.", show_alert=True)
        return

    try:
        idx = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    if idx < 0 or idx >= len(game.answers):
        await callback.answer("Нет такого варианта.", show_alert=True)
        return

    winner_answer = game.answers[idx]
    winner_id = winner_answer.user_id

    # Генерируем картинку
    out_dir = Path("generated")
    out_path = out_dir / f"round_{game.round_no}_{winner_id}.png"
    await generate_image_file(game.current_situation or "", winner_answer.text, out_path)

    game.phase = "result"
    await callback.message.answer(
        f"🏆 Победитель раунда: <a href=\"tg://user?id={winner_id}\">{winner_id}</a>\n"
        f"Его ответ: <b>{winner_answer.text}</b>",
        parse_mode="HTML"
    )
    try:
        await callback.message.answer_photo(photo=out_path.open("rb"))
    except Exception:
        await callback.message.answer("(Изображение не удалось отправить, но файл сгенерирован.)")

    # Следующий раунд
    game.next_host()
    game.current_situation = None
    game.answers.clear()
    game.phase = "lobby"

    await callback.message.answer(
        "Раунд завершён. Ведущий передан по кругу.\n"
        "Запусти следующий раунд: /start_round"
    )
    await callback.answer()


# =====================  ТАЙМАУТ СБОРА ОТВЕТОВ  =====================

async def round_timeout_watchdog(chat_id: int, delay: int):
    await asyncio.sleep(delay)
    game = GAMES.get(chat_id)
    if not game or game.phase != "collect":
        return
    if not game.answers:
        await router.bot.send_message(chat_id, "⏰ Время вышло, ответов нет. Запусти /start_round ещё раз.")
        game.phase = "lobby"
        return
    await router.bot.send_message(chat_id, "⏰ Время вышло. Показываю, что успели отправить…")
    await show_answers_for_all_by_chat(chat_id)


# =====================  РЕГИСТРАЦИЯ  =====================

def register_game_handlers(dp):
    load_situations_cards()
    dp.include_router(router)

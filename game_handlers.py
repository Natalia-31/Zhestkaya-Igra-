from __future__ import annotations
import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from PIL import Image, ImageDraw, ImageFont
import openai
import os

# =====================  НАСТРОЙКИ  =====================
MIN_PLAYERS = 2
HAND_SIZE = 10
ROUND_TIMEOUT = 40

try:
    BASE_DIR = Path(__file__).parent
except NameError:
    BASE_DIR = Path(".").resolve()

FONT_PATH = BASE_DIR / "arial.ttf"

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY не найден в окружении!")

openai.api_key = os.getenv("OPENAI_API_KEY")

# =====================  РОУТЕР  =====================
router = Router()

# =====================  МОДЕЛИ  =====================
@dataclass
class Answer:
    user_id: int
    text: str
    user_name: str

@dataclass
class GameState:
    chat_id: int
    players: Dict[int, str] = field(default_factory=dict)
    host_index: int = 0
    phase: str = "lobby"
    round_no: int = 0
    current_situation: Optional[str] = None
    answers: List[Answer] = field(default_factory=list)
    hands: Dict[int, List[str]] = field(default_factory=dict)
    deck: List[str] = field(default_factory=list)

    @property
    def player_ids(self) -> List[int]:
        return list(self.players.keys())

    def current_host_id(self) -> Optional[int]:
        if not self.player_ids:
            return None
        return self.player_ids[self.host_index % len(self.player_ids)]

    def current_host_name(self) -> Optional[str]:
        host_id = self.current_host_id()
        if host_id:
            return self.players.get(host_id, f"ID: {host_id}")
        return None

    def next_host(self):
        if self.players:
            self.host_index = (self.host_index + 1) % len(self.players)

# =====================  ГЛОБАЛЬНОЕ СОСТОЯНИЕ  =====================
GAMES: Dict[int, GameState] = {}

# =====================  OPENAI: Генерация =====================
def generate_situations_sync(count: int = 5) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких забавных ситуаций для карточной игры. "
        f"Каждая должна содержать пропуск '____'. Например:\n"
        f"Самая странная причина, по которой я опоздал: ____."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.9,
        )
        text = response.choices[0].message.content.strip()
        situations = [line.strip("- •\t ") for line in text.split("\n") if "____" in line]
        return situations[:count]
    except Exception as e:
        print(f"Ошибка генерации ситуаций через OpenAI: {e}")
        return ["Ошибка генерации ситуации."]

async def generate_situations_via_openai(count: int = 5) -> List[str]:
    return await asyncio.to_thread(generate_situations_sync, count)

def generate_cards_sync(count: int = 50) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких смешных ответов для карточной игры. "
        f"Каждый не длиннее трёх слов. Примеры: «моя мама», «утренний секс», «кошачья мята»."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.9,
        )
        text = response.choices[0].message.content.strip()
        cards = [line.strip("- •\t ") for line in text.split("\n") if line.strip()]
        return cards[:count]
    except Exception as e:
        print(f"Ошибка генерации карт через OpenAI: {e}")
        return [f"Ответ #{i+1}" for i in range(count)]

async def generate_cards_via_openai(count: int = 50) -> List[str]:
    return await asyncio.to_thread(generate_cards_sync, count)

# =====================  УТИЛИТЫ  =====================
def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE and game.deck:
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"👉 {card[:35]}", callback_data=f"ans:{idx}")]
            for idx, card in enumerate(hand)
        ]
    )

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Выбрать #{i+1}", callback_data=f"pick:{i}")]
            for i, _ in enumerate(answers)
        ]
    )

def answers_summary(answers: List[Answer]) -> str:
    if not answers:
        return "Ответов пока нет."
    return "Ответы игроков:\n\n" + "\n".join(
        f"#{i+1}: {a.text} (от: {a.user_name})" for i, a in enumerate(answers)
    )

# =====================  ХЕНДЛЕРЫ  =====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это «Жесткая Игра» 🎮\n\n"
        "Команды:\n"
        "• /new_game — создать игру\n"
        "• /join — присоединиться\n"
        "• /start_round — начать раунд"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer("🃏 Новая игра создана! Жмите /join чтобы присоединиться.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user:
        return
    if user.id in game.players:
        await message.reply("Ты уже в игре!")
        return
    game.players[user.id] = user.full_name
    deal_to_full_hand(game, user.id)
    await message.answer(f"✅ {user.full_name} присоединился. Всего игроков: {len(game.players)}")

# (дальше идут обработчики раунда и callback — они у тебя уже есть, менять там ничего не надо кроме вызова OpenAI как я сделал выше)

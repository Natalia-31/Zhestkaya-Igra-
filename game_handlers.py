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

# Генерация простой картинки по «ситуация + ответ»
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
    """Подгрузить ситуации и карты из файлов, если они есть; иначе — примеры."""
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

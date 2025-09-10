from __future__ import annotations
import asyncio
import random
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from aiogram import Router, F, Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

from config import GAME_SETTINGS, CONTENT_MODES

# =====================  НАСТРОЙКИ  =====================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
FONT_PATH = BASE_DIR / "arial.ttf"

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в окружении!")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise RuntimeError("OPENAI_API_KEY не найден в окружении!")
client = OpenAI(api_key=OPENAI_KEY)

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
router = Router()

# =====================  FALLBACK =====================
def load_fallback_cards() -> List[str]:
    if CONTENT_MODES.get("adult_mode"):
        path = DATA_DIR / "cards_adult.json"
    else:
        path = DATA_DIR / "cards.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["cards"]
    except Exception:
        return ["заглушка"]

def load_fallback_situations() -> List[str]:
    if CONTENT_MODES.get("adult_mode"):
        path = DATA_DIR / "situations_adult.json"
    else:
        path = DATA_DIR / "situations.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["situations"]
    except Exception:
        return ["Ситуация-заглушка: ____"]

# =====================  OPENAI =====================
def generate_situations_sync(count: int = 5) -> List[str]:
    prompt = (
        f"Сгенерируй {count} смешных ситуаций для игры. "
        f"Каждая должна содержать плейсхолдер '____'. "
        f"Примеры:\nЕсли бы не ____, я бы бросил пить.\n"
        f"Три вещи в рюкзаке: ____, ____ и чувство вины."
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=800,
        )
        text = resp.choices[0].message.content.strip()
        return [line for line in text.split("\n") if "____" in line][:count]
    except Exception as e:
        print(f"Ошибка генерации ситуаций: {e}")
        return []

async def generate_situations(count: int = 5) -> List[str]:
    return await asyncio.to_thread(generate_situations_sync, count)

def generate_cards_sync(count: int = 50) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких и смешных ответов (до трёх слов). "
        f"Примеры: моя мама, запах носков, утренний секс."
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=800,
        )
        text = resp.choices[0].message.content.strip()
        return [line for line in text.split("\n") if line][:count]
    except Exception as e:
        print(f"Ошибка генерации ответов: {e}")
        return []

async def generate_cards(count: int = 50) -> List[str]:
    return await asyncio.to_thread(generate_cards_sync, count)

# =====================  УТИЛИТЫ =====================
def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < GAME_SETTINGS["cards_per_hand"] and game.deck:
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str], chat_id: int) -> InlineKeyboardMarkup:
    rows = []
    for idx, card in enumerate(hand):
        txt = (card[:35] + "…") if len(card) > 35 else card
        rows.append([InlineKeyboardButton(text=f"👉 {txt}", callback_data=f"ans:{chat_id}:{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Выбрать #{i+1}", callback_data=f"pick:{i}")]
            for i in range(len(answers))
        ]
    )

def answers_summary(answers: List[Answer]) -> str:
    return "Ответы:\n\n" + "\n".join(f"#{i+1}: {a.text} ({a.user_name})" for i,a in enumerate(answers))

# =====================  ХЕНДЛЕРЫ =====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это «Жесткая Игра» 🎮\n\n"
        "/new_game — создать лобби\n"
        "/join — присоединиться\n"
        "/start_round — начать раунд"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer("🃏 Новая игра создана!\nЖми /join, чтобы присоединиться.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    u = message.from_user
    if not u:
        return
    if u.id in game.players:
        await message.reply("Ты уже в игре!")
        return
    game.players[u.id] = u.full_name
    await message.answer(f"✅ {u.full_name} присоединился.\nИгроков: {len(game.players)}")

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < GAME_SETTINGS["min_players"]:
        await message.answer(f"Нужно минимум {GAME_SETTINGS['min_players']} игроков.")
        return
    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()

    situations = await generate_situations(1)
    if not situations:
        situations = load_fallback_situations()
    game.current_situation = random.choice(situations)

    deck = await generate_cards(50)
    if not deck:
        deck = load_fallback_cards()
    game.deck = deck
    random.shuffle(game.deck)

    await message.answer(
        f"🎬 Раунд #{game.round_no}\n"
        f"Ведущий: {game.current_host_name()}\n\n"
        f"Ситуация: {game.current_situation}\n\n"
        f"Игроки, выбирайте ответы!"
    )

    for uid in game.player_ids:
        if uid != game.current_host_id():
            game.hands[uid] = []
            deal_to_full_hand(game, uid)
            await send_hand_to_player(message.bot, game, uid)

async def send_hand_to_player(bot: Bot, game: GameState, user_id: int):
    hand = game.hands.get(user_id, [])
    if not hand:
        return
    kb = make_answers_keyboard(hand, chat_id=game.chat_id)
    try:
        await bot.send_message(user_id, "Ваша рука:", reply_markup=kb)
    except Exception:
        print(f"⚠️ Игрок {user_id} не открыл ЛС с ботом.")

@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery, bot: Bot):
    try:
        _, chat_id_str, idx_str = callback.data.split(":")
        chat_id = int(chat_id_str)
        idx = int(idx_str)
    except:
        await callback.answer("Ошибка кнопки.", show_alert=True)
        return

    game = GAMES.get(chat_id)
    if not game or game.phase != "collect":
        await callback.answer("Раунд не активен.", show_alert=True)
        return

    u = callback.from_user
    if any(a.user_id == u.id for a in game.answers):
        await callback.answer("Ты уже ответил.", show_alert=True)
        return
    if u.id == game.current_host_id():
        await callback.answer("Ведущий не играет.", show_alert=True)
        return

    hand = game.hands.get(u.id, [])
    if not (0 <= idx < len(hand)):
        await callback.answer("Нет такой карты.", show_alert=True)
        return

    card = hand.pop(idx)
    game.answers.append(Answer(user_id=u.id, text=card, user_name=u.full_name))
    deal_to_full_hand(game, u.id)

    await callback.answer("Ответ принят!")
    await bot.send_message(chat_id, f"✅ {u.full_name} сделал выбор.")

    need = len([p for p in game.player_ids if p != game.current_host_id()])
    if len(game.answers) >= need:
        await show_answers_for_all(bot, chat_id)

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    random.shuffle(game.answers)
    game.phase = "choose"
    kb = make_choices_keyboard(game.answers)
    await bot.send_message(chat_id,
        f"🧾 Ситуация:\n{game.current_situation}\n\n" + answers_summary(game.answers),
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery, bot: Bot):
    game = GAMES.get(callback.message.chat.id)
    if not game or game.phase != "choose":
        return
    u = callback.from_user
    if u.id != game.current_host_id():
        await callback.answer("Выбирать может только ведущий.", show_alert=True)
        return
    idx = int(callback.data.split(":")[1])
    winner = game.answers[idx]
    await callback.message.edit_text(
        f"🏆 Победил {winner.user_name} с ответом: {winner.text}"
    )
    game.next_host()
    game.phase = "lobby"

# =====================  ЗАПУСК  =====================
def register_game_handlers(dp):
    dp.include_router(router)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    register_game_handlers(dp)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")

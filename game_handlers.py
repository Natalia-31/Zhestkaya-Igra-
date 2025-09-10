# handlers/game_handlers.py
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
ROUND_TIMEOUT = 60

try:
    BASE_DIR = Path(__file__).parent.parent
except NameError:
    BASE_DIR = Path(".").resolve()

FONT_PATH = BASE_DIR / "arial.ttf"

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OpenAI API ключ не найден! Установите OPENAI_API_KEY.")

router = Router()

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
        return self.players.get(self.current_host_id(), None)

    def next_host(self):
        if self.players:
            self.host_index = (self.host_index + 1) % len(self.players)

GAMES: Dict[int, GameState] = {}

# ===== OpenAI генерирует ситуации =====
def generate_situations_sync(count: int = 1) -> List[str]:
    prompt = (
        f"Сгенерируй {count} короткую забавную ситуацию для карточной игры. "
        f"В ней должен быть один пропуск '____'. Верни только строку ситуации."
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            max_tokens=200,
            temperature=0.9,
        )
        text = resp.choices[0].message.content.strip()
        lines = [line for line in text.split("\n") if "____" in line]
        return lines[:count]
    except Exception as e:
        print(f"Ошибка генерации ситуации: {e}")
        return ["На вечеринке я неожиданно ____."]

async def generate_situations_via_openai(count: int = 1) -> List[str]:
    return await asyncio.to_thread(generate_situations_sync, count)

# ===== OpenAI генерирует ответы (карты) =====
def generate_cards_sync(count: int = 50) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких смешных ответов для карточной игры, "
        f"каждый не более трёх слов. Примеры: «моя мама», «запах гениталий», «утренний секс»."
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            max_tokens=400,
            temperature=1.0,
        )
        text = resp.choices[0].message.content.strip()
        cards = [line for line in text.split("\n") if line.strip()]
        return cards[:count]
    except Exception as e:
        print(f"Ошибка генерации ответов: {e}")
        return [f"Ответ #{i+1}" for i in range(count)]

async def generate_cards_via_openai(count: int = 50) -> List[str]:
    return await asyncio.to_thread(generate_cards_sync, count)

# ===== Утилиты игры =====
def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE and game.deck:
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"👉 {card}", callback_data=f"ans:{i}")]
               for i, card in enumerate(hand)]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"{i+1}. {ans.text}", callback_data=f"pick:{i}")]
               for i, ans in enumerate(answers)]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def answers_summary(answers: List[Answer]) -> str:
    lines = [f"{i+1}. {a.text} (от {a.user_name})" for i, a in enumerate(answers)]
    return "Ответы:\n" + "\n".join(lines)

async def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    try:
        out_path.parent.mkdir(exist_ok=True, parents=True)
        img = Image.new("RGB", (800, 400), color=(30,30,30))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(FONT_PATH), 24) if FONT_PATH.exists() else ImageFont.load_default()
        text = situation.replace("____", answer)
        draw.text((10, 10), text, fill="white", font=font)
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
        return None

# ===== Хендлеры =====
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это «Жесткая Игра».\n"
        "/new_game — создать игру\n"
        "/join — присоединиться\n"
        "/start_round — начать раунд"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer("Новая игра создана! Жмите /join.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user or user.id in game.players:
        return await message.reply("Нельзя присоединиться.")
    game.players[user.id] = user.full_name
    await message.answer(f"{user.full_name} присоединился. Всего: {len(game.players)}")

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        return await message.answer("Недостаточно игроков.")
    if game.phase != "lobby":
        return await message.answer("Раунд уже идёт.")
    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()

    await message.answer("Генерирую ситуацию и карты...")
    sit, cards = await generate_situations_via_openai(1), await generate_cards_via_openai(50)
    game.current_situation = sit[0]
    game.deck = cards
    random.shuffle(game.deck)

    await message.answer(f"Раунд {game.round_no}\nСитуация:\n{game.current_situation}")
    for uid in game.player_ids:
        if uid != game.current_host_id():
            deal_to_full_hand(game, uid)
            await message.bot.send_message(uid, "Ваша рука:", reply_markup=make_answers_keyboard(game.hands[uid]))

    asyncio.create_task(round_timeout_watchdog(message.bot, message.chat.id, game.round_no))

@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery):
    game = ensure_game(callback.message.chat.id)
    user = callback.from_user
    if game.phase != "collect":
        return await callback.answer("Сейчас не время отвечать.", show_alert=True)
    idx = int(callback.data.split(":")[1])
    hand = game.hands.get(user.id, [])
    if idx < 0 or idx >= len(hand):
        return await callback.answer("Неверная карта.", show_alert=True)
    card = hand.pop(idx)
    game.answers.append(Answer(user_id=user.id, text=card, user_name=user.full_name))
    await callback.answer("Ответ принят.")
    await callback.message.delete()
    if len(game.answers) == len(game.player_ids)-1:
        await show_answers_for_all(callback.message.bot, callback.message.chat.id)

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    if game.phase != "collect":
        return
    game.phase = "choose"
    text = f"Ситуация:\n{game.current_situation}\n\n" + answers_summary(game.answers)
    await bot.send_message(chat_id, text, reply_markup=make_choices_keyboard(game.answers))

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery):
    game = ensure_game(callback.message.chat.id)
    if game.phase != "choose":
        return await callback.answer("Сейчас не время выбирать.", show_alert=True)
    idx = int(callback.data.split(":")[1])
    winner = game.answers[idx]
    await callback.message.edit_text(f"Победитель: {winner.user_name}\nОтвет: {winner.text}")
    out = BASE_DIR / "generated" / f"round_{game.round_no}.png"
    img_path = await generate_image_file(game.current_situation, winner.text, out)
    if img_path:
        await callback.message.bot.send_photo(game.chat_id, FSInputFile(img_path))
    game.next_host()
    game.phase = "lobby"
    await callback.message.bot.send_message(game.chat_id, f"Раунд завершён. Новый ведущий: {game.current_host_name()}")

async def round_timeout_watchdog(bot: Bot, chat_id: int, round_no: int):
    await asyncio.sleep(ROUND_TIMEOUT)
    game = GAMES.get(chat_id)
    if game and game.round_no == round_no and game.phase == "collect":
        await bot.send_message(chat_id, "⏰ Время вышло!")
        await show_answers_for_all(bot, chat_id)

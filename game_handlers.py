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
    phase: str = "lobby"  # lobby, collect, choose
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

GAMES: Dict[int, GameState] = {}

def generate_situations_sync(count: int = 5) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких забавных ситуаций для игры, "
        f"каждая ситуация с пропуском '____'. Верни только ситуации по одной на строку."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.9,
            n=1,
        )
        text = response.choices[0].message.content.strip()
        situations = [line.strip("- \u2022\t ") for line in text.split("\n") if "____" in line]
        if situations:
            return situations[:count]
        else:
            return ["На вечеринке я неожиданно ____."]
    except Exception as e:
        print(f"Ошибка генерации ситуаций: {e}")
        return ["Ошибка генерации ситуации."]

async def generate_situations_via_openai(count: int = 5) -> List[str]:
    return await asyncio.to_thread(generate_situations_sync, count)

def generate_cards_sync(count: int = 50) -> List[str]:
    prompt = (
        f"Сгенерируй {count} коротких смешных ответов для игры, "
        f"каждый максимум три слова, примеры: «моя мама», «запах гениталий», «утренний секс». "
        f"Верни ответы списком по одному на строку без нумерации и тире."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=1.0,
            n=1,
        )
        text = response.choices[0].message.content.strip()
        cards = [line.strip("- \u2022\t0123456789.") for line in text.split("\n") if line.strip()]
        return cards[:count] if cards else get_default_cards(count)
    except Exception as e:
        print(f"Ошибка генерации ответов: {e}")
        return get_default_cards(count)

def get_default_cards(count: int) -> List[str]:
    default = [
        "моя мама", "запах гениталий", "утренний секс", "пьяный енот", "квантовый скачок",
        "мамкин борщ", "грязные носки", "бывший парень", "сломанный унитаз", "живот учителя"
    ]
    cards = default * (count // len(default) + 1)
    random.shuffle(cards)
    return cards[:count]

async def generate_cards_via_openai(count: int = 50) -> List[str]:
    return await asyncio.to_thread(generate_cards_sync, count)

def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def find_game_by_user(user_id: int) -> Optional[GameState]:
    for game in GAMES.values():
        if user_id in game.players:
            return game
    return None

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE and game.deck:
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"👉 {card}", callback_data=f"ans:{idx}")] for idx, card in enumerate(hand)]
    )

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"{idx+1}. {ans.text}", callback_data=f"pick:{idx}")] for idx, ans in enumerate(answers)]
    )

def answers_summary(answers: List[Answer]) -> str:
    return "\n".join(f"{i+1}. {a.text} (от {a.user_name})" for i, a in enumerate(answers))

async def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (800, 400), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(FONT_PATH), 24) if FONT_PATH.exists() else ImageFont.load_default()
        text = situation.replace("____", answer)
        lines = []
        max_width = 750
        words = text.split()
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            width, _ = draw.textsize(test_line, font=font)
            if width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        y = 50
        for line in lines:
            draw.text((25, y), line, fill="white", font=font)
            y += 30
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
        return None

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
    await message.answer("🃏 Новая игра создана! Присоединяйтесь через /join.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user or user.id in game.players:
        return await message.reply("Невозможно присоединиться.")
    game.players[user.id] = user.full_name
    await message.answer(f"✅ {user.full_name} присоединился. Всего: {len(game.players)}")

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        return await message.answer(f"Нужно минимум {MIN_PLAYERS} игроков.")
    if game.phase != "lobby":
        return await message.answer("Раунд уже идёт.")
    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()

    situations = await generate_situations_via_openai(5)
    game.current_situation = random.choice(situations) if situations else "Не удалось сгенерировать ситуацию."

    game.deck = await generate_cards_via_openai()
    random.shuffle(game.deck)

    host_name = game.current_host_name()

    await message.answer(
        f"🎬 Раунд #{game.round_no}\n"
        f"👑 Ведущий: <b>{host_name}</b>\n\n"
        f"📜 Ситуация:\n<b>{game.current_situation}</b>\n\n"
        f"Игроки, выбирайте ответы! У вас {ROUND_TIMEOUT} секунд.",
        parse_mode="HTML"
    )

    for uid in game.player_ids:
        if uid != game.current_host_id():
            game.hands[uid] = []
            deal_to_full_hand(game, uid)
            await send_hand_to_player(message.bot, game, uid)

    asyncio.create_task(round_timeout_watchdog(message.bot, message.chat.id, game.round_no))

async def send_hand_to_player(bot: Bot, game: GameState, user_id: int):
    hand = game.hands.get(user_id, [])
    if not hand:
        try:
            await bot.send_message(user_id, "У вас закончились карты!")
        except Exception:
            pass
        return
    kb = make_answers_keyboard(hand)
    try:
        await bot.send_message(user_id, "Ваша рука. Выберите карту-ответ:", reply_markup=kb)
    except Exception as e:
        print(f"Не удалось отправить руку игроку {user_id}: {e}")

@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery):
    user = callback.from_user
    game = find_game_by_user(user.id)
    if not game:
        return await callback.answer("Вы не участвуете в игре.", show_alert=True)
    if game.phase != "collect":
        return await callback.answer("Сейчас не время отвечать.", show_alert=True)
    if user.id == game.current_host_id():
        return await callback.answer("Ведущий не может отвечать.", show_alert=True)
    if any(a.user_id == user.id for a in game.answers):
        return await callback.answer("Ты уже отправил ответ.", show_alert=True)
    try:
        idx = int(callback.data.split(":")[1])
        hand = game.hands.get(user.id, [])
        if idx < 0 or idx >= len(hand):
            return await callback.answer("Неверная карта.", show_alert=True)
        card = hand.pop(idx)
        game.answers.append(Answer(user_id=user.id, text=card, user_name=user.full_name))
        await callback.answer("Ответ принят!")
        await callback.message.delete()
        await callback.message.bot.send_message(game.chat_id, f"✅ {user.full_name} сделал(а) свой выбор.")
        expecting = len([p for p in game.player_ids if p != game.current_host_id()])
        if len(game.answers) >= expecting:
            await show_answers_for_all(callback.message.bot, game.chat_id)
    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора карты.", show_alert=True)

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    if game.phase != "collect":
        return
    game.phase = "choose"
    random.shuffle(game.answers)
    if not game.answers:
        await bot.send_message(chat_id, "Никто не ответил. Начинайте новый раунд /start_round")
        game.phase = "lobby"
        game.next_host()
        return
    text = (
        f"📜 Ситуация:\n<b>{game.current_situation}</b>\n\n"
        f"Ответы игроков:\n{answers_summary(game.answers)}\n\n"
        f"👑 Ведущий ({game.current_host_name()}), выбирай лучший ответ!"
    )
    await bot.send_message(chat_id, text, reply_markup=make_choices_keyboard(game.answers), parse_mode="HTML")

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery):
    game = ensure_game(callback.message.chat.id)
    user = callback.from_user
    if game.phase != "choose":
        return await callback.answer("Сейчас не время выбирать.", show_alert=True)
    if user.id != game.current_host_id():
        return await callback.answer("Выбирать может только ведущий.", show_alert=True)
    try:
        idx = int(callback.data.split(":")[1])
        winner = game.answers[idx]
        await callback.message.edit_text(
            f"🏆 Ведущий ({game.current_host_name()}) выбрал лучший ответ!\n\n"
            f"Победитель раунда: <b>{winner.user_name}</b>\n"
            f"С ответом: «<b>{winner.text}</b>»\n\nГенерирую картинку...",
            parse_mode="HTML",
            reply_markup=None
        )
        out = BASE_DIR / "generated" / f"round_{game.round_no}.png"
        img_path = await generate_image_file(game.current_situation, winner.text, out)
        if img_path:
            await callback.message.bot.send_photo(
                game.chat_id,
                FSInputFile(img_path),
                caption=f"Ситуация: {game.current_situation}\nОтвет: {winner.text}"
            )
        game.next_host()
        game.phase = "lobby"
        await callback.message.bot.send_message(
            game.chat_id,
            f"Раунд завершён!\nНовый ведущий: <b>{game.current_host_name()}</b>.\n"
            "Чтобы начать следующий раунд, нажмите /start_round",
            parse_mode="HTML"
        )
        await callback.answer()
    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора победителя.", show_alert=True)

async def round_timeout_watchdog(bot: Bot, chat_id: int, round_no: int):
    await asyncio.sleep(ROUND_TIMEOUT)
    game = GAMES.get(chat_id)
    if game and game.round_no == round_no and game.phase == "collect":
        game.phase = "choose"
        await bot.send_message(chat_id, "⏰ Время вышло! Показываю, что успели отправить…")
        await show_answers_for_all(bot, chat_id)

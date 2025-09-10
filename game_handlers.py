from __future__ import annotations
import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
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
import json
import os
import openai

# =====================  НАСТРОЙКИ  =====================
MIN_PLAYERS = 2
HAND_SIZE = 10
ROUND_TIMEOUT = 60

try:
    # Определение базовой директории для поиска файлов
    BASE_DIR = Path(__file__).parent.parent
except NameError:
    BASE_DIR = Path(".").resolve()

FONT_PATH = BASE_DIR / "arial.ttf"  # Путь к файлу шрифта

# Настройка OpenAI (если используется для генерации изображений)
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("ВНИМАНИЕ: OpenAI API ключ не найден! Генерация изображений через OpenAI будет недоступна.")

router = Router()

# =====================  Загрузка данных из JSON =====================
def load_json_list(filepath: str) -> List[str]:
    """Загружает список строк из JSON-файла."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"Файл {filepath} успешно загружен, {len(data)} записей.")
                return data
            else:
                print(f"ОШИБКА: {filepath} должен содержать список (array).")
                return []
    except FileNotFoundError:
        print(f"ОШИБКА: Файл {filepath} не найден.")
        return []
    except json.JSONDecodeError:
        print(f"ОШИБКА: Неверный формат JSON в файле {filepath}.")
        return []
    except Exception as e:
        print(f"Не удалось загрузить {filepath}: {e}")
        return []

all_situations = load_json_list("situations.json")
all_cards = load_json_list("cards.json")


# =====================  Классы для состояния игры =====================
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
    used_situations: Set[str] = field(default_factory=set)
    used_cards: Set[str] = field(default_factory=set)

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


# =====================  Ключевые функции логики игры =====================
def get_random_unused_situation(game: GameState) -> str:
    # Сначала пытаемся получить неиспользованные ситуации из глобального списка
    unused = [s for s in all_situations if s not in game.used_situations]
    
    # Если неиспользованных не осталось, сбрасываем счетчик и берем все заново
    if not unused and all_situations:
        game.used_situations.clear()
        unused = all_situations.copy()
        
    # КРИТИЧЕСКАЯ ПРОВЕРКА: если список все равно пуст (файл не загрузился)
    if not unused:
        print("ВНИМАНИЕ: Список ситуаций пуст! Используется резервная ситуация.")
        return "Резервная жесткая ситуация: ____." # Возвращаем запасной вариант, чтобы игра не сломалась
        
    # Выбираем случайную ситуацию из доступных
    situation = random.choice(unused)
    game.used_situations.add(situation)
    return situation

def get_deck_without_used(game: GameState) -> List[str]:
    """Формирует колоду для раунда из неиспользованных карт."""
    available = [c for c in all_cards if c not in game.used_cards]
    if len(available) < (len(game.players) * HAND_SIZE):
        game.used_cards.clear()
        available = all_cards.copy()
    
    if not available:
        print("ВНИМАНИЕ: Список карт пуст! Используются резервные карты.")
        return [f"Резервная карта #{i}" for i in range(50)]

    deck_size = min(len(available), 100) # Берем до 100 карт в колоду на раунд
    deck = random.sample(available, deck_size)
    for card in deck:
        game.used_cards.add(card)
    return deck

def ensure_game(chat_id: int) -> GameState:
    """Возвращает или создает состояние игры для чата."""
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def find_game_by_user(user_id: int) -> Optional[GameState]:
    """Находит игру, в которой участвует пользователь."""
    for game in GAMES.values():
        if user_id in game.players:
            return game
    return None

def deal_to_full_hand(game: GameState, user_id: int):
    """Раздает игроку карты до полного размера руки."""
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE and game.deck:
        hand.append(game.deck.pop())


# =====================  Создание клавиатур =====================
def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"👉 {card}", callback_data=f"ans:{idx}")]
        for idx, card in enumerate(hand)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{idx+1}. {ans.text}", callback_data=f"pick:{idx}")]
        for idx, ans in enumerate(answers)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =====================  Вспомогательные функции =====================
def answers_summary(answers: List[Answer]) -> str:
    """Формирует текст со списком ответов."""
    return "\n".join(f"{i+1}. {a.text}" for i, a in enumerate(answers))

async def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    """Генерирует изображение с текстом ситуации и ответа."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (800, 400), (25, 25, 25))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(str(FONT_PATH), 32) if FONT_PATH.exists() else ImageFont.load_default()
        
        # Обертка текста
        text = situation.replace("____", f'"{answer}"')
        lines = []
        max_width = 750
        words = text.split(' ')
        current_line = ""
        for word in words:
            if draw.textlength(current_line + word + ' ', font=font) <= max_width:
                current_line += word + ' '
            else:
                lines.append(current_line)
                current_line = word + ' '
        lines.append(current_line)
        
        # Центрирование текста
        total_height = len(lines) * font.getbbox("A")[3]
        y_start = (400 - total_height) / 2
        
        for i, line in enumerate(lines):
            y = y_start + i * (font.getbbox("A")[3] + 5)
            draw.text((40, y), line.strip(), fill="white", font=font)
            
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
        return None

# =====================  Обработчики команд и колбэков =====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это «Жесткая Игра».\n"
        "/new_game — создать новую игру\n"
        "/join — присоединиться к игре\n"
        "/start_round — начать новый раунд"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer("🃏 Новая игра создана! Другие игроки могут присоединиться через /join.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user: return
    if user.id in game.players:
        return await message.reply("Вы уже в игре.")
    
    game.players[user.id] = user.full_name
    await message.answer(f"✅ {user.full_name} присоединился! Всего игроков: {len(game.players)}")

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        return await message.answer(f"Недостаточно игроков. Нужно минимум {MIN_PLAYERS}.")
    if game.phase != "lobby":
        return await message.answer("Раунд уже идет. Дождитесь его окончания.")
        
    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()
    game.current_situation = get_random_unused_situation(game)
    game.deck = get_deck_without_used(game)

    host_name = game.current_host_name()

    await message.answer(
        f"🎬 **Раунд #{game.round_no}**\n"
        f"👑 Ведущий: **{host_name}**\n\n"
        f"📜 **Ситуация:**\n_{game.current_situation}_\n\n"
        f"Игроки, выбирайте лучшие ответы! У вас {ROUND_TIMEOUT} секунд.",
        parse_mode="Markdown"
    )

    for uid in game.player_ids:
        if uid != game.current_host_id():
            deal_to_full_hand(game, uid)
            await send_hand_to_player(message.bot, game, uid)

    asyncio.create_task(round_timeout_watchdog(message.bot, message.chat.id, game.round_no))

async def send_hand_to_player(bot: Bot, game: GameState, user_id: int):
    hand = game.hands.get(user_id, [])
    if not hand:
        try:
            await bot.send_message(user_id, "У вас закончились карты!")
        except Exception: pass
        return

    try:
        await bot.send_message(user_id, "Ваша рука. Выберите карту:", reply_markup=make_answers_keyboard(hand))
    except Exception as e:
        print(f"Не удалось отправить руку игроку {user_id}: {e}")

@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery):
    user = callback.from_user
    game = find_game_by_user(user.id)
    
    if not (game and user): return
    if game.phase != "collect":
        return await callback.answer("Сейчас не время отвечать.", show_alert=True)
    if user.id == game.current_host_id():
        return await callback.answer("Ведущий не может отвечать.", show_alert=True)
    if any(a.user_id == user.id for a in game.answers):
        return await callback.answer("Вы уже сделали свой выбор.", show_alert=True)

    try:
        idx = int(callback.data.split(":")[1])
        hand = game.hands.get(user.id, [])
        card = hand.pop(idx)
        game.answers.append(Answer(user_id=user.id, text=card, user_name=user.full_name))
        
        await callback.answer("Ответ принят!", show_alert=False)
        await callback.message.delete()
        await callback.message.bot.send_message(game.chat_id, f"✅ {user.full_name} сделал(а) свой выбор.")

        expecting_answers = len(game.player_ids) - 1
        if len(game.answers) >= expecting_answers:
            await show_answers_for_all(callback.message.bot, game.chat_id)
            
    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора карты.", show_alert=True)

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    if game.phase != "collect": return
    game.phase = "choose"
    
    if not game.answers:
        await bot.send_message(chat_id, "Никто не ответил. Раунд завершен. Начинайте новый через /start_round")
        game.phase = "lobby"
        game.next_host()
        return

    random.shuffle(game.answers)
    text = (
        f"📜 **Ситуация:**\n_{game.current_situation}_\n\n"
        f"**Ответы игроков:**\n{answers_summary(game.answers)}\n\n"
        f"👑 Ведущий ({game.current_host_name()}), выбирай лучший ответ!"
    )
    await bot.send_message(chat_id, text, reply_markup=make_choices_keyboard(game.answers), parse_mode="Markdown")

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery):
    user = callback.from_user
    game = ensure_game(callback.message.chat.id)
    if not user: return
    
    if game.phase != "choose":
        return await callback.answer("Сейчас не время выбирать.", show_alert=True)
    if user.id != game.current_host_id():
        return await callback.answer("Только ведущий может выбирать победителя.", show_alert=True)

    try:
        idx = int(callback.data.split(":")[1])
        winner = game.answers[idx]
        
        await callback.message.edit_text(
            f"🏆 Ведущий ({game.current_host_name()}) выбрал!\n\n"
            f"Победитель раунда: **{winner.user_name}**\n"
            f"С ответом: «_{winner.text}_»\n\n",
            parse_mode="Markdown",
            reply_markup=None
        )

        out_path = BASE_DIR / "generated" / f"round_{game.round_no}.png"
        img_path = await generate_image_file(game.current_situation, winner.text, out_path)
        if img_path:
            await callback.message.reply_photo(FSInputFile(img_path))

        game.next_host()
        game.phase = "lobby"
        await callback.message.bot.send_message(
            game.chat_id,
            f"Раунд завершён! Новый ведущий: **{game.current_host_name()}**.\n"
            "Чтобы начать следующий раунд, используйте /start_round",
            parse_mode="Markdown"
        )
        await callback.answer()
    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора победителя.", show_alert=True)

async def round_timeout_watchdog(bot: Bot, chat_id: int, round_no: int):
    """Следит за временем раунда и завершает его, если время вышло."""
    await asyncio.sleep(ROUND_TIMEOUT)
    game = GAMES.get(chat_id)
    if game and game.round_no == round_no and game.phase == "collect":
        await bot.send_message(chat_id, "⏰ Время вышло! Показываю ответы, которые успели прислать…")
        await show_answers_for_all(bot, chat_id)

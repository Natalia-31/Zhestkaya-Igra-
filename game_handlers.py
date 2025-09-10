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
ROUND_TIMEOUT = 60 # Дадим игрокам минуту на ответ

# Правильный путь к корневой папке проекта
try:
    BASE_DIR = Path(__file__).parent.parent
except NameError:
    BASE_DIR = Path(".").resolve()

FONT_PATH = BASE_DIR / "arial.ttf"

# API ключ OpenAI
# Убедитесь, что переменная окружения OPENAI_API_KEY установлена
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OpenAI API ключ не найден! Установите OPENAI_API_KEY.")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =====================  РОУТЕР  =====================
router = Router()

# =====================  МОДЕЛИ ДАННЫХ  =====================
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
    phase: str = "lobby" # lobby, collect, choose
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
        return self.players.get(host_id) if host_id else None

    def next_host(self):
        if self.players:
            self.host_index = (self.host_index + 1) % len(self.players)

# =====================  ГЛОБАЛЬНОЕ СОСТОЯНИЕ ИГРЫ  =====================
GAMES: Dict[int, GameState] = {}

# =====================  OPENAI: Генерация контента =====================
def generate_situations_sync(count: int = 1) -> List[str]:
    prompt = f"Сгенерируй {count} остроумную и смешную ситуацию для карточной игры. Ситуация должна содержать пропуск '____' для ответа игрока. Ответ должен быть одной строкой."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.9,
        )
        text = response.choices[0].message.content.strip()
        return [line.strip("- •\t") for line in text.split("\n") if "____" in line]
    except Exception as e:
        print(f"Ошибка генерации ситуаций: {e}")
        return ["На вечеринке инопланетян я случайно ____."]

def generate_cards_sync(count: int = 50) -> List[str]:
    prompt = f"Сгенерируй {count} коротких, смешных и немного абсурдных ответов для карточной игры. Каждый ответ - не более 3 слов. Примеры: 'пьяный енот', 'квантовый скачок', 'мамкин борщ'. Ответы должны быть в именительном падеже."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=1.0,
        )
        text = response.choices[0].message.content.strip()
        return [line.strip("- •\t") for line in text.split("\n") if line.strip()]
    except Exception as e:
        print(f"Ошибка генерации ответов: {e}")
        return [f"Ответ #{i+1}" for i in range(count)]

async def generate_content_for_round() -> tuple[str, list[str]]:
    situation_task = asyncio.to_thread(generate_situations_sync, 1)
    cards_task = asyncio.to_thread(generate_cards_sync, 50)
    results = await asyncio.gather(situation_task, cards_task)
    situation = results[0][0] if results[0] else "Не удалось сгенерировать ситуацию."
    cards = results[1]
    return situation, cards

# =====================  УТИЛИТЫ ИГРЫ =====================
def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE and game.deck:
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👉 {card[:35]}", callback_data=f"ans:{idx}")] for idx, card in enumerate(hand)
    ])

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Выбрать: {ans.text[:25]}", callback_data=f"pick:{idx}")] for idx, ans in enumerate(answers)
    ])

def answers_summary(answers: List[Answer]) -> str:
    if not answers: return "Ответов пока нет."
    return "Ответы игроков:\n\n" + "\n".join(f"🕵️‍♂️ {a.text} (от {a.user_name})" for a in answers)

async def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1024, 512), color=(25, 25, 25))
        draw = ImageDraw.Draw(img)
        try:
            font_sit = ImageFont.truetype(str(FONT_PATH), 48)
            font_ans = ImageFont.truetype(str(FONT_PATH), 64)
        except IOError:
            font_sit = ImageFont.load_default()
            font_ans = ImageFont.load_default()

        # Центрирование текста
        sit_text = situation.replace("____", answer)
        draw.text((512, 150), sit_text, fill=(255, 255, 255), font=font_sit, anchor="ms")
        draw.text((512, 300), answer.upper(), fill=(255, 255, 0), font=font_ans, anchor="ms")

        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
        return None


# =====================  ОСНОВНЫЕ ХЕНДЛЕРЫ ИГРЫ =====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🔥 Привет! Это «Жесткая Игра» — аналог 500 злобных карт.\n\n"
        "Как играть:\n"
        "• `/new_game` — создать лобби в этом чате.\n"
        "• `/join` — присоединиться к игре.\n"
        "• Ведущий прошлой игры запускает новый раунд командой `/start_round`.\n"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer("🃏 Новая игра создана! Присоединяйтесь командой /join.")

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user: return
    if user.id in game.players:
        return await message.reply("Ты уже в игре! ✋")
    game.players[user.id] = user.full_name
    await message.answer(f"✅ {user.full_name} присоединился. Всего игроков: {len(game.players)}")

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        return await message.answer(f"Нужно минимум {MIN_PLAYERS} игрока, а вас {len(game.players)}.")
    if game.phase != "lobby":
        return await message.answer("Раунд уже идет. Дождитесь его окончания.")

    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()

    msg = await message.answer("✨ Генерирую новую ситуацию и карты... Минутку.")
    
    game.current_situation, game.deck = await generate_content_for_round()
    random.shuffle(game.deck)

    await msg.edit_text(
        f"🎬 **Раунд #{game.round_no}**\n\n"
        f"👑 Ведущий: **{game.current_host_name()}**\n\n"
        f"📜 Ситуация: **{game.current_situation}**\n\n"
        f"Игроки, выбирайте карты в личных сообщениях! У вас {ROUND_TIMEOUT} секунд.",
        parse_mode="Markdown"
    )

    for uid in game.player_ids:
        if uid != game.current_host_id():
            deal_to_full_hand(game, uid)
            await send_hand_to_player(message.bot, game, uid)

    asyncio.create_task(round_timeout_watchdog(message.bot, message.chat.id, game.round_no))

async def send_hand_to_player(bot: Bot, game: GameState, user_id: int):
    hand = game.hands.get(user_id, [])
    if not hand: return
    try:
        await bot.send_message(
            user_id, "Ваша рука. Выберите карту-ответ:",
            reply_markup=make_answers_keyboard(hand)
        )
    except Exception as e:
        print(f"Не удалось отправить руку игроку {user_id}: {e}")

@router.callback_query(F.data.startswith("ans:"))
async def cb_pick_answer(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    game = ensure_game(callback.message.chat.id if callback.message else list(GAMES.keys())[0])

    if game.phase != "collect":
        return await callback.answer("Сейчас не время отвечать.", show_alert=True)
    if user.id not in game.players:
        return await callback.answer("Ты не в игре.", show_alert=True)
    if any(a.user_id == user.id for a in game.answers):
        return await callback.answer("Ты уже отправил ответ.", show_alert=True)
    if user.id == game.current_host_id():
        return await callback.answer("Ведущий не может отвечать.", show_alert=True)

    try:
        idx = int(callback.data.split(":")[1])
        hand = game.hands.get(user.id, [])
        if not (0 <= idx < len(hand)):
            return await callback.answer("Ошибка выбора карты.", show_alert=True)

        card_text = hand.pop(idx)
        game.answers.append(Answer(user_id=user.id, text=card_text, user_name=user.full_name))
        
        await callback.answer("Ответ принят!", show_alert=False)
        await callback.message.delete()
        await bot.send_message(game.chat_id, f"✅ {user.full_name} сделал(а) свой выбор.")

        expecting = len([p for p in game.player_ids if p != game.current_host_id()])
        if len(game.answers) >= expecting:
            await show_answers_for_all(bot, game.chat_id)
    except (ValueError, IndexError) as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    if game.phase != "collect": return # Предотвращаем двойной вызов
    
    game.phase = "choose"
    random.shuffle(game.answers)
    
    if not game.answers:
        await bot.send_message(chat_id, "Никто не ответил. Начинайте новый раунд /start_round")
        game.phase = "lobby"
        game.next_host()
        return

    text = (
        f"📜 Ситуация: **{game.current_situation}**\n\n"
        + answers_summary(game.answers)
        + f"\n\n👑 Ведущий ({game.current_host_name()}), выбирай лучший ответ!"
    )
    await bot.send_message(chat_id, text, reply_markup=make_choices_keyboard(game.answers), parse_mode="Markdown")

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery, bot: Bot):
    game = ensure_game(callback.message.chat.id)
    user = callback.from_user

    if game.phase != "choose":
        return await callback.answer("Сейчас не время выбирать.", show_alert=True)
    if user.id != game.current_host_id():
        return await callback.answer("Выбирать может только ведущий.", show_alert=True)

    try:
        idx = int(callback.data.split(":")[1])
        winner_answer = game.answers[idx]
        
        await callback.message.edit_text(
            f"🏆 Победитель раунда: **{winner_answer.user_name}** с ответом «**{winner_answer.text}**»!\n\nГенерирую картинку...",
            parse_mode="Markdown", reply_markup=None
        )
        
        out_path = BASE_DIR / "generated" / f"round_{game.round_no}.png"
        if await generate_image_file(game.current_situation or "", winner_answer.text, out_path):
            await bot.send_photo(game.chat_id, photo=FSInputFile(out_path))
        
        game.next_host()
        game.phase = "lobby"
        await bot.send_message(
            game.chat_id,
            f"Раунд завершён!\nНовый ведущий: **{game.current_host_name()}**.\nДля следующего рауnda жми /start_round",
            parse_mode="Markdown"
        )
        await callback.answer()
    except (ValueError, IndexError) as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)


async def round_timeout_watchdog(bot: Bot, chat_id: int, round_no: int):
    await asyncio.sleep(ROUND_TIMEOUT)
    game = GAMES.get(chat_id)
    # Проверяем, что раунд все еще тот же и фаза не сменилась
    if game and game.round_no == round_no and game.phase == "collect":
        await bot.send_message(chat_id, "⏰ Время вышло! Показываю, что успели отправить…")
        await show_answers_for_all(bot, chat_id)

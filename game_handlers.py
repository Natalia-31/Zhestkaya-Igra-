from __future__ import annotations
import asyncio
import json
import random
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

# =====================  НАСТРОЙКИ  =====================
MIN_PLAYERS = 1  # Для тестирования - 1 игрок
HAND_SIZE = 10
ROUND_TIMEOUT = 40

try:
    BASE_DIR = Path(__file__).parent
except NameError:
    BASE_DIR = Path(".").resolve()

CARDS_PATH = BASE_DIR / "cards.json"
FONT_PATH = BASE_DIR / "arial.ttf"

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
ALL_CARDS: List[str] = []

# =====================  ЗАГРУЗКА КАРТ  =====================
def load_cards():
    global ALL_CARDS
    try:
        if CARDS_PATH.exists():
            data = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
            cards = list(data.get("cards", []))
            if cards:
                ALL_CARDS = cards
            else:
                raise Exception("Файл cards.json пуст.")
        else:
            raise Exception("Файл cards.json не найден.")
    except Exception as ex:
        raise Exception(f"Ошибка загрузки карт: {ex}")

load_cards()

# =====================  БЛОК ГЕНЕРАЦИИ СИТУАЦИЙ  =====================
SITUATION_TEMPLATES = [
    "На утро после вечеринки я обнаружил в своей постели ____. ",
    "Самая странная причина, по которой я опоздал на работу: ____.",
    "В коробке с подарком я нашёл ____. ",
    "Секрет моего успеха — это ____. ",
    "Мой внутренний голос звучит как ____. ",
]

FILLERS = [
    "курицу в костюме",
    "горящий тостер",
    "потерянные носки",
    "мистерия в шкафу",
    "странный шёпот ночью",
]

def generate_new_situation() -> str:
    template = random.choice(SITUATION_TEMPLATES)
    filler = random.choice(FILLERS)
    return template.replace("____", filler)

# =====================  УТИЛИТЫ  =====================
def ensure_game(chat_id: int) -> GameState:
    return GAMES.setdefault(chat_id, GameState(chat_id=chat_id))

def deal_to_full_hand(game: GameState, user_id: int):
    hand = game.hands.setdefault(user_id, [])
    while len(hand) < HAND_SIZE:
        if not game.deck:
            game.deck = ALL_CARDS.copy()
            random.shuffle(game.deck)
        if not game.deck:
            break
        hand.append(game.deck.pop())

def make_answers_keyboard(hand: List[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👉 {card[:35]}...", callback_data=f"ans:{idx}")]
        for idx, card in enumerate(hand)
    ])

def make_choices_keyboard(answers: List[Answer]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Выбрать #{idx}", callback_data=f"pick:{idx-1}")]
        for idx, _ in enumerate(answers, 1)
    ])

def answers_summary(answers: List[Answer]) -> str:
    if not answers:
        return "Ответов пока нет."
    lines = [f"#{i+1}: {a.text} (от: {a.user_name})" for i, a in enumerate(answers)]
    return "Ответы игроков:\n\n" + "\n".join(lines)

async def generate_image_file(situation: str, answer: str, out_path: Path) -> Optional[Path]:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1024, 1024), color=(245, 246, 248))
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype(str(FONT_PATH), 42)
            font_body = ImageFont.truetype(str(FONT_PATH), 36)
        except IOError:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        draw.text((40, 40), "Жесткая Игра", fill=(20, 20, 20), font=font_title)

        def wrap(text: str, width: int = 30) -> List[str]:
            words, lines, buf = text.split(), [], []
            for w in words:
                buf.append(w)
                if len(" ".join(buf)) > width:
                    lines.append(" ".join(buf[:-1]))
                    buf = [w]
            if buf: lines.append(" ".join(buf))
            return lines

        y = 120
        draw.text((40, y), "Ситуация:", fill=(40, 40, 40), font=font_body); y += 40
        for line in wrap(situation):
            draw.text((60, y), line, fill=(10, 10, 10), font=font_body); y += 40
        y += 20
        draw.text((40, y), "Ответ:", fill=(40, 40, 40), font=font_body); y += 40
        for line in wrap(answer):
            draw.text((60, y), line, fill=(10, 10, 10), font=font_body); y += 40

        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Ошибка генерации изображения: {e}")
        return None

async def show_answers_for_all(bot: Bot, chat_id: int):
    game = ensure_game(chat_id)
    if not game.answers:
        await bot.send_message(chat_id, "Ответов нет — показывать нечего.")
        return

    random.shuffle(game.answers)
    game.phase = "choose"
    
    text = (
        f"🧾 Ситуация:\n<b>{game.current_situation}</b>\n\n"
        + answers_summary(game.answers)
        + f"\n\nВедущий ({game.current_host_name()}) выбирает лучший ответ."
    )
    kb = make_choices_keyboard(game.answers)
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

# =====================  ХЕНДЛЕРЫ  =====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Это «Жесткая Игра».\n\n"
        "Как играть:\n"
        "• /new_game — создать лобби\n"
        "• /join — присоединиться\n"
        "• /start_round — начать раунд\n"
    )

@router.message(Command("new_game"))
async def cmd_new_game(message: Message):
    GAMES[message.chat.id] = GameState(chat_id=message.chat.id)
    await message.answer(
        "🃏 Новая игра создана!\n"
        "Жми /join, чтобы присоединиться.\n"
        "Когда все соберутся, можно начать раунд: /start_round."
    )

@router.message(Command("join"))
async def cmd_join(message: Message):
    game = ensure_game(message.chat.id)
    user = message.from_user
    if not user:
        return

    if user.id in game.players:
        await message.reply("Ты уже в игре! ✋")
        return

    game.players[user.id] = user.full_name
    deal_to_full_hand(game, user.id)
    await message.answer(
        f"✅ {user.full_name} присоединился.\n"
        f"Игроков сейчас: {len(game.players)}"
    )

@router.message(Command("start_round"))
async def cmd_start_round(message: Message):
    game = ensure_game(message.chat.id)
    if len(game.players) < MIN_PLAYERS:
        await message.answer(f"Нужно минимум {MIN_PLAYERS} игрока, а вас {len(game.players)}.")
        return
    if game.phase != "lobby":
        await message.answer("Раунд уже идет. Дождитесь его окончания.")
        return

    game.phase = "collect"
    game.round_no += 1
    game.answers.clear()

    # Используем генератор ситуаций
    game.current_situation = generate_new_situation()

    host_name = game.current_host_name()

    await message.answer(
        f"🎬 Раунд #{game.round_no}\n"
        f"Ведущий: <b>{host_name}</b>\n\n"
        f"Ситуация:\n<b>{game.current_situation}</b>\n\n"
        f"Игроки, выбирайте ответы! У вас {ROUND_TIMEOUT} секунд.",
        parse_mode="HTML"
    )

    for uid in game.player_ids:
        if uid != game.current_host_id():
            await send_hand_to_player(message.bot, game, uid)

    asyncio.create_task(round_timeout_watchdog(message.bot, message.chat.id, ROUND_TIMEOUT))

async def send_hand_to_player(bot: Bot, game: GameState, user_id: int):
    hand = game.hands.get(user_id, [])
    if not hand:
        deal_to_full_hand(game, user_id)
        hand = game.hands[user_id]
    
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
async def cb_pick_answer(callback: CallbackQuery, bot: Bot):
    if not callback.message:
        return
    game = ensure_game(callback.message.chat.id)
    user = callback.from_user

    if game.phase != "collect":
        await callback.answer("Сейчас не время отвечать.", show_alert=True)
        return
    if user.id not in game.players:
        await callback.answer("Ты не в игре. Нажми /join в группе.", show_alert=True)
        return
    if any(a.user_id == user.id for a in game.answers):
        await callback.answer("Ты уже отправил ответ.", show_alert=True)
        return
    if user.id == game.current_host_id():
        await callback.answer("Ведущий не может отвечать.", show_alert=True)
        return

    try:
        idx = int(callback.data.split(":")[1])
        hand = game.hands.get(user.id, [])
        if not (0 <= idx < len(hand)):
            await callback.answer("Нет такой карты.", show_alert=True)
            return
        
        card_text = hand.pop(idx)
        game.answers.append(Answer(user_id=user.id, text=card_text, user_name=user.full_name))
        deal_to_full_hand(game, user.id)
        
        await callback.answer("Ответ принят!", show_alert=False)
        await callback.message.delete()

        await bot.send_message(game.chat_id, f"✅ {user.full_name} сделал(а) свой выбор.")

        expecting = len([p for p in game.player_ids if p != game.current_host_id()])
        if len(game.answers) >= expecting:
            await show_answers_for_all(bot, game.chat_id)

    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора карты.", show_alert=True)

@router.callback_query(F.data.startswith("pick:"))
async def cb_pick_winner(callback: CallbackQuery, bot: Bot):
    if not callback.message:
        return
    game = ensure_game(callback.message.chat.id)
    user = callback.from_user

    if game.phase != "choose":
        await callback.answer("Сейчас не время выбирать.", show_alert=True)
        return
    if user.id != game.current_host_id():
        await callback.answer("Выбирать может только ведущий.", show_alert=True)
        return

    try:
        idx = int(callback.data.split(":")[1])
        winner_answer = game.answers[idx]
        winner_name = winner_answer.user_name

        await callback.message.edit_text(
            f"🏆 Ведущий ({game.current_host_name()}) выбрал лучший ответ!\n\n"
            f"Победитель раунда: <b>{winner_name}</b>\n"
            f"С ответом: «<b>{winner_answer.text}</b>»\n\nГенерирую картинку...",
            parse_mode="HTML",
            reply_markup=None
        )

        out_path = BASE_DIR / "generated" / f"round_{game.round_no}.png"
        
        if await generate_image_file(game.current_situation or "", winner_answer.text, out_path):
            try:
                await bot.send_photo(
                    chat_id=game.chat_id,
                    photo=FSInputFile(out_path),
                    caption=f"Ситуация: {game.current_situation}\nОтвет: {winner_answer.text}"
                )
            except Exception as e:
                await bot.send_message(game.chat_id, f"(Не удалось отправить изображение: {e})")
        else:
            await bot.send_message(game.chat_id, "(Не удалось сгенерировать изображение.)")
        
        game.next_host()
        game.phase = "lobby"
        await bot.send_message(
            game.chat_id,
            "Раунд завершён!\n"
            f"Новый ведущий: <b>{game.current_host_name()}</b>.\n"
            "Чтобы начать следующий раунд, нажмите /start_round",
            parse_mode="HTML"
        )
        await callback.answer()

    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора победителя.", show_alert=True)

async def round_timeout_watchdog(bot: Bot, chat_id: int, delay: int):
    await asyncio.sleep(delay)
    game = GAMES.get(chat_id)
    if not game or game.phase != "collect":
        return
    
    await bot.send_message(chat_id, "⏰ Время вышло! Показываю, что успели отправить…")
    await show_answers_for_all(bot, chat_id)

def register_game_handlers(dp):
    dp.include_router(router)

async def main():
    bot = Bot(token="ВАШ_ТОКЕН")
    dp = Dispatcher()
    register_game_handlers(dp)
    
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")

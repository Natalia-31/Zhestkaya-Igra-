# В файлах game_handlers.py и admin_handlers.py
from game_utils import decks, gen

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

# Обратите внимание, импортируем объект decks
from game_utils import decks

ADMIN_IDS = [270104288] # Вставьте сюда ваш ID

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

@router.message(Command("reload"))
async def cmd_reload(message: Message):
    """Перезагружает колоды ситуаций и ответов."""
    try:
        # Создаем новый экземпляр, чтобы перечитать файлы
        new_decks = decks.__class__()
        decks.situations = new_decks.situations
        decks.answers = new_decks.answers
        
        situations_count = len(decks.situations)
        answers_count = len(decks.answers)
        
        await message.answer(
            f"✅ Колоды успешно перезагружены!\n"
            f"Ситуаций: {situations_count}\n"
            f"Ответов: {answers_count}"
        )
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при перезагрузке: {e}")

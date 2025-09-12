# handlers/admin_handlers.py

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from game_utils import gen # Импортируем наш глобальный генератор

# Замените на ID администраторов
# Можете взять его из вашего .env файла
ADMIN_IDS = [270104288] # Пример, вставьте сюда ваш ID

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS)) # Все команды в этом файле только для админов

@router.message(Command("reload"))
async def cmd_reload(message: Message):
    """
    Обработчик команды /reload для перезагрузки списка ситуаций.
    """
    try:
        count = gen.reload_situations()
        await message.answer(f"✅ Ситуации успешно перезагружены!\nЗагружено новых ситуаций: {count}")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при перезагрузке: {e}")


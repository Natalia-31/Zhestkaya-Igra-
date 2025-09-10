from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_utils import send_random_situation_with_image, get_random_situation

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Стартовая команда."""
    await message.answer(
        "🎮 **Добро пожаловать в Жесткую Игру!**\n\n"
        "Это весёлая игра с ситуациями и изображениями!\n\n"
        "**Доступные команды:**\n"
        "• `/start_round` - начать раунд с ситуацией и изображением\n"
        "• `/situation` - получить случайную ситуацию\n"
        "• `/test_image` - тест генерации изображения\n"
        "• `/help` - показать эту справку",
        parse_mode="Markdown"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам."""
    await message.answer(
        "🎮 **Жесткая Игра - Справка**\n\n"
        "**Команды:**\n"
        "• `/start_round` - запуск нового раунда\n"
        "• `/situation` - получить только текст ситуации\n"
        "• `/test_image` - протестировать генерацию изображения\n\n"
        "**Как играть:**\n"
        "1. Запустите раунд командой /start_round\n"
        "2. Получите ситуацию и изображение к ней\n"
        "3. Придумайте креативный ответ!\n"
        "4. Веселитесь! 🎉",
        parse_mode="Markdown"
    )

@router.message(Command("start_round"))
async def start_game_round(message: Message):
    """Начинает новый раунд с ситуацией и изображением."""
    try:
        # Отправляем вводный текст
        await message.answer(
            "🎮 **Начинаем новый раунд Жесткой Игры!**\n\n"
            "Сейчас я покажу вам ситуацию и сгенерирую к ней изображение...",
            parse_mode="Markdown"
        )
        
        # Отправляем ситуацию с изображением
        success = await send_random_situation_with_image(
            message.bot, 
            message.chat.id
        )
        
        if success:
            await message.answer(
                "✅ **Готово!** Теперь игроки могут отвечать на ситуацию!\n\n"
                "Придумайте самый креативный и смешной ответ! 🎯",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "⚠️ Произошла ошибка при генерации изображения, но игра продолжается!\n\n"
                "Используйте команду `/situation` чтобы получить новую ситуацию.",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"❌ Ошибка в обработчике раунда: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске раунда. Попробуйте еще раз через несколько секунд."
        )

@router.message(Command("situation"))
async def get_situation_only(message: Message):
    """Получить только текст ситуации без изображения."""
    try:
        situation = get_random_situation()
        await message.answer(
            f"🎲 **Случайная ситуация:**\n\n_{situation}_\n\n"
            f"Используйте `/start_round` для получения ситуации с изображением!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Ошибка получения ситуации: {e}")
        await message.answer("❌ Ошибка получения ситуации. Попробуйте позже.")

@router.message(Command("test_image"))
async def test_image_generation(message: Message):
    """Тестовая команда для проверки генерации изображений."""
    try:
        await message.answer("🎨 **Тестирую генерацию изображения...**\n\nЭто может занять до 30 секунд.")
        
        success = await send_random_situation_with_image(
            message.bot,
            message.chat.id
        )
        
        if not success:
            await message.answer(
                "❌ **Ошибка генерации изображения**\n\n"
                "Возможные причины:\n"
                "• Неверный OPENAI_API_KEY\n"
                "• Превышен лимит запросов\n"
                "• Проблемы с интернет-соединением\n\n"
                "Проверьте настройки и попробуйте позже."
            )
        else:
            await message.answer("✅ **Тест успешно пройден!** Генерация изображений работает корректно.")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        await message.answer("❌ Ошибка при тестировании генерации изображений.")

# Обработчик неизвестных команд
@router.message()
async def unknown_command(message: Message):
    """Обработка неизвестных команд."""
    await message.answer(
        "🤔 Не понимаю эту команду.\n\n"
        "Используйте `/help` для просмотра доступных команд.",
        parse_mode="Markdown"
    )

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from game_utils import send_random_situation_with_image, get_random_situation

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Стартовая команда."""
    await message.answer(
        "🎮 **Добро пожаловать в Жесткую Игру!**\n\n"
        "Доступные команды:\n"
        "• `/start_round` - начать раунд с ситуацией и изображением\n"
        "• `/situation` - получить случайную ситуацию\n"
        "• `/test_image` - тест генерации изображения",
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
                "✅ Готово! Теперь игроки могут отвечать на ситуацию!",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "⚠️ Произошла ошибка при генерации изображения, но игра продолжается!",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"❌ Ошибка в обработчике раунда: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске раунда. Попробуйте еще раз."
        )

@router.message(Command("situation"))
async def get_situation_only(message: Message):
    """Получить только текст ситуации без изображения."""
    situation = get_random_situation()
    await message.answer(
        f"🎲 **Случайная ситуация:**\n\n_{situation}_",
        parse_mode="Markdown"
    )

@router.message(Command("test_image"))
async def test_image_generation(message: Message):
    """Тестовая команда для проверки генерации изображений."""
    await message.answer("🎨 Тестирую генерацию изображения...")
    
    success = await send_random_situation_with_image(
        message.bot,
        message.chat.id
    )
    
    if not success:
        await message.answer("❌ Ошибка генерации изображения. Проверьте настройки OpenAI API.")

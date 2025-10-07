# card_generator.py
import requests
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os

# Используем ключи из окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Модели
gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")  # Для текста (шутки)

def generate_pollinations_image(situation, answer):
    """
    Генерирует изображение через Pollinations.ai (запасной вариант)
    """
    prompt = (
        f"Digital board game card illustration for situation: '{situation}'. "
        f"Answer: '{answer}'. Minimalism, Russian board game style, only image, no text."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.url if response.status_code == 200 else None
    except Exception as e:
        print(f"⚠️ Pollinations error: {e}")
        return None

def generate_gemini_image(situation: str, answer: str) -> str:
    """
    Генерирует изображение через Gemini Imagen 3
    
    Args:
        situation: Текст ситуации
        answer: Текст ответа игрока
        
    Returns:
        Путь к временному файлу изображения или None
    """
    try:
        if not GEMINI_API_KEY:
            print("⚠️ GEMINI_API_KEY не найден! Добавьте в переменные окружения.")
            return None
        
        print(f"🎨 Генерируем изображение через Gemini Imagen 3...")
        
        # Промпт для мема на русском
        prompt = (
            f"Создай забавную иллюстрацию для карточной игры в стиле мема. "
            f"Ситуация: '{situation}'. Ответ игрока: '{answer}'. "
            f"Стиль: яркие цвета, минимализм, юмор, карикатура. "
            f"Без текста на изображении!"
        )
        
        # Используем Gemini для генерации изображения через prompt
        response = gemini_model.generate_content([
            prompt,
            "Создай изображение в формате мема для этой ситуации"
        ])
        
        # Проверяем есть ли изображение в ответе
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        # Ищем изображение в частях ответа
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Сохраняем изображение
                            image_data = part.inline_data.data
                            
                            # Создаем временный файл
                            import hashlib
                            file_hash = hashlib.md5((situation + answer).encode()).hexdigest()[:10]
                            temp_path = f"temp_image_{file_hash}.png"
                            
                            # Декодируем base64 и сохраняем
                            import base64
                            image_bytes = base64.b64decode(image_data)
                            
                            with open(temp_path, 'wb') as f:
                                f.write(image_bytes)
                            
                            print(f"✅ Изображение создано через Gemini: {temp_path}")
                            return temp_path
        
        print("⚠️ Gemini не вернул изображение в ответе")
        return None
        
    except Exception as e:
        print(f"❌ Ошибка генерации через Gemini: {e}")
        return None

def generate_card_joke(situation, answer):
    """
    Генерирует саркастическую шутку для игры через Gemini
    """
    try:
        prompt = (
            f"Придумай саркастическую шутку для настольной игры. "
            f"Ситуация: '{situation}', ответ игрока: '{answer}'. "
            f"Формат: 1–2 строки, остроумно, иронично, по-русски."
        )
        response = gemini_model.generate_content(prompt)
        return response.text if response else "😅 У меня закончились шутки!"
    except Exception as e:
        print(f"⚠️ Ошибка генерации шутки: {e}")
        return "😅 Шутка не загрузилась!"

def create_situation_card(situation_text: str, template_path: str = 'assets/card_template.png') -> BytesIO:
    """
    Создает карточку ситуации с текстом на шаблоне
    
    Args:
        situation_text: Текст ситуации
        template_path: Путь к шаблону карточки
        
    Returns:
        BytesIO объект с готовой карточкой
    """
    # Открываем шаблон
    try:
        card = Image.open(template_path).convert('RGB')
    except FileNotFoundError:
        # Если шаблон не найден, создаем белую карточку
        card = Image.new('RGB', (864, 1184), 'white')
        print(f"⚠️ Шаблон не найден: {template_path}, создана пустая карточка")
    
    draw = ImageDraw.Draw(card)
    
    # Загружаем шрифт Stalinist One с поддержкой кириллицы
    font_paths = [
        'assets/fonts/StalinistOne-Regular.ttf',  # Stalinist One (приоритет)
        'assets/fonts/RussoOne-Regular.ttf',  # Резервный
        'assets/fonts/DejaVuSans.ttf',  # Резервный
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
        'C:\\Windows\\Fonts\\arial.ttf',  # Windows (исправлены слэши)
        '/System/Library/Fonts/Helvetica.ttc',  # macOS
    ]
    
    font = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, 38)  # Размер 38 для Stalinist One
            print(f"✅ Шрифт загружен: {font_path}")
            break
        except Exception as e:
            continue
    
    if font is None:
        font = ImageFont.load_default()
        print("⚠️ Шрифт не найден, используется шрифт по умолчанию")
    
    # Параметры карточки
    card_width, card_height = card.size
    max_width = card_width - 150  # Отступы по краям (увеличено для крупного шрифта)
    
    # Разбиваем текст на строки
    words = situation_text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]
        
        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "
    
    # Добавляем последнюю строку
    if current_line:
        lines.append(current_line.strip())
    
    # Ограничиваем количество строк
    max_lines = 9
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if len(lines[-1]) > 50:
            lines[-1] = lines[-1][:50] + "..."
    
    # Центрируем текст по вертикали
    line_height = 52  # Увеличенный интервал для лучшей читаемости
    total_height = len(lines) * line_height
    y_start = (card_height - total_height) // 2
    
    # Рисуем каждую строку
    y_position = y_start
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x_position = (card_width - text_width) // 2
        
        # Рисуем текст черным цветом
        draw.text((x_position, y_position), line, fill=(0, 0, 0), font=font)
        y_position += line_height
    
    # Сохраняем в BytesIO
    bio = BytesIO()
    bio.name = 'situation_card.png'
    card.save(bio, 'PNG')
    bio.seek(0)
    
    return bio

import requests
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os

# Используем ключ из окружения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-09-2025")

def generate_pollinations_image(situation, answer):
    prompt = (
        f"Digital board game card illustration for situation: '{situation}'. "
        f"Answer: '{answer}'. Minimalism, Russian board game style, only image, no text."
    )
    url = "https://api.pollinations.ai/prompt"
    params = {"prompt": prompt}
    response = requests.get(url, params=params)
    return response.url if response.status_code == 200 else None

def generate_card_joke(situation, answer):
    prompt = (
        f"Придумай саркастическую шутку для настольной игры. "
        f"Ситуация: '{situation}', ответ игрока: '{answer}'. "
        f"Формат: 1–2 строки, остроумно, иронично, по-русски."
    )
    response = gemini_model.generate_content(prompt)
    return response.text if response else "😅 У меня закончились шутки!"

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

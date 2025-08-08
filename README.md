# 🎭 Жесткая Игра - Telegram Bot

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-Latest-blue)](https://core.telegram.org/bots/api)

Русская версия знаменитой игры **Cards Against Humanity** для Telegram. Веселитесь с друзьями прямо в мессенджере!

## ✨ Особенности

- 🎮 **Полная игровая механика** Cards Against Humanity
- 👥 **До 10 игроков** в одной игре
- 🔞 **Два режима**: семейный и взрослый контент
- 🖼️ **Генерация изображений** для выигрышных комбинаций
- 🛠️ **Админская панель** для управления контентом
- 💾 **SQLite база данных** с полной статистикой
- 📱 **Удобный интерфейс** с inline-кнопками

## 🚀 Быстрый старт

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/your-username/zhestkaya-igra-bot.git
cd zhestkaya-igra-bot
```

### 2. Установите зависимости
```bash
pip install -r requirements.txt
```

### 3. Настройте бота
1. Создайте бота у [@BotFather](https://t.me/BotFather)
2. Скопируйте токен
3. Отредактируйте `config.py`:
```python
BOT_TOKEN = "ваш_токен_здесь"
ADMIN_IDS = [ваш_telegram_id]
```

### 4. Запустите бота
```bash
python main.py
```

## 🎯 Как играть

### В Telegram группе:
1. Добавьте бота в группу
2. Выполните `/new_game` 
3. Выберите режим игры (👨‍👩‍👧‍👦 семейный или 🔞 взрослый)
4. Игроки присоединяются через `/join` или кнопку
5. При наличии 3+ игроков нажмите "▶️ Начать игру"

### Игровой процесс:
- **Ведущий** получает ситуацию с пропуском (\_\_\_)
- **Игроки** получают карты в личные сообщения и выбирают ответ
- **Ведущий** выбирает самую смешную комбинацию
- Победитель получает очко, следующий раунд с новым ведущим

## 📋 Команды

### Для игроков:
- `/start` - Приветствие и помощь
- `/new_game` - Создать новую игру
- `/join` - Присоединиться к игре
- `/help` - Правила и команды
- `/stats` - Личная статистика

### Для администраторов:
- `/admin` - Админская панель
- `/add_situation <текст с ___> [adult]` - Добавить ситуацию
- `/add_card <текст> [adult]` - Добавить карту-ответ
- `/stats_global` - Глобальная статистика
- `/reload_data` - Перезагрузить данные

## 📁 Структура проекта

```
zhestkaya_igra_bot/
├── main.py                 # 🚀 Точка входа
├── config.py               # ⚙️ Конфигурация
├── database/
│   └── models.py          # 💾 Модели SQLite
├── game/
│   ├── logic.py           # 🎯 Игровая логика
│   └── image_generator.py # 🖼️ Генерация изображений
├── handlers/
│   ├── game_handlers.py   # 🎮 Обработчики игры
│   ├── admin_handlers.py  # 🛠️ Админские команды
│   └── utils.py          # 🔧 Утилиты
├── data/
│   ├── situations.json    # 📝 Ситуации
│   └── cards.json        # 🃏 Карты-ответы
└── requirements.txt       # 📦 Зависимости
```

## 📝 Лицензия

Проект распространяется под [MIT License](LICENSE) - используйте свободно!

---

<div align="center">
<b>Приятной игры! 🎭🎮</b><br>
Если проект понравился, поставьте ⭐ звезду!
</div>

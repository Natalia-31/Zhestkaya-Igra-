# game_utils.py

import os
import json
import random
from pathlib import Path
from typing import List, Optional
from io import BytesIO
import asyncio
import aiohttp
from urllib.parse import quote
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile

# ===========================
# ВСТАВЬТЕ СЮДА ФУНКЦИЮ create_prompt
# ===========================
def create_prompt(situation: str, answer: str) -> str:
    """Создает детальный промпт с контекстом для лучшей генерации."""
    translations = {
        # ситуации
        "Меня взяли на работу, потому что я умею": "I got hired because I can",
        "Лучшее оправдание для сна на работе": "Best excuse for sleeping at work",
        "Если бы суперсила выбирала меня": "If I had a superpower it would be",
        "Самое нелепое происшествие в школе": "Most ridiculous thing that happened at school",
        "Идеальный подарок на день рождения": "Perfect birthday gift",
        "Мой секретный талант": "My secret talent",
        "То, что точно не стоит писать в резюме": "Something you should never put in your resume",
        "Главный кулинарный шедевр моего детства": "My greatest childhood cooking masterpiece",
        # ответы
        "бесконечный запас пельменей": "infinite supply of dumplings",
        "говорящий кактус": "talking cactus",
        "очень злой хомяк": "very angry hamster",
        "квантовый двигатель от жигулей": "quantum engine from old Russian car",
        "армия боевых пингвинов": "army of combat penguins",
        "потерянные носки": "lost socks from another dimension",
        "секретная база на Луне": "secret moon base",
        "грустный тромбон": "sad trombone",
        "кибер-бабушка с лазерными глазами": "cyber grandma with laser eyes",
        "дракон, работающий бухгалтером": "dragon working as accountant",
        "невидимый велосипед": "invisible bicycle",
        "портал в страну розовых пони": "portal to pink pony land",
        "картофельное ополчение": "potato militia",
        "забытый пароль от Вселенной": "forgotten password to the Universe",
        "робот-пылесос, захвативший мир": "robot vacuum that conquered the world",
        "философский камень": "philosopher's stone that turned out to be regular pebble",
        "енот, ворующий мемы": "raccoon stealing memes",
        "подозрительно умный голубь": "suspiciously smart pigeon",
        "котенок, который случайно запустил ядерные ракеты": "kitten who accidentally launched nuclear missiles"
    }
    situation_en = situation.replace("____", "").strip()
    for ru, en in translations.items():
        if ru in situation_en:
            situation_en = situation_en.replace(ru, en)
            break
    answer_en = answer.strip()
    for ru, en in translations.items():
        if ru in answer_en:
            answer_en = en
            break
    # автоперевод, если остался русский
    if any(ord(c) > 127 for c in situation_en):
        try:
            from googletrans import Translator
            situation_en = Translator().translate(situation_en, dest='en').text
        except:
            pass
    if any(ord(c) > 127 for c in answer_en):
        try:
            from googletrans import Translator
            answer_en = Translator().translate(answer_en, dest='en').text
        except:
            pass
    scene_description = f"{situation_en} {answer_en}"
    style_modifiers = [
        "funny cartoon illustration", "humorous scene", "absurd comedy",
        "whimsical digital art", "colorful and vibrant",
        "comedic situation", "high quality illustration", "detailed funny scene"
    ]
    final_prompt = f"{scene_description}, {', '.join(style_modifiers)}"
    print(f"📝 [Финальный промпт] {final_prompt}")
    return final_prompt

# ===========================
# ДАЛЕЕ — ваш существующий код:
# DeckManager, GameImageGenerator и т.д.
# в методе send_illustration используйте create_prompt:
# prompt = create_prompt(situation, answer)
# ===========================

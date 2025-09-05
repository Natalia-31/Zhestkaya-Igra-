from aiogram import Router, types, F
from aiogram.filters import Command
import json
import random
import aiohttp

router = Router()

game_state = {
    "players": [],
    "host_index": 0,
    "round_answers": {},
    "current_situation": None,
    "current_options": [],
    "phase": "waiting"
}

def load_situations():
    with open('situations.json', 'r', encoding='utf-8') as f:
        return json.load(f)

situations = load_situations()

async def generate_image(prompt):
    # Заглушка генерации изображения.
    # Замените этот блок на реальный запрос к DALL·E или другому генератору!
    # Например, к API OpenAI DALL·E или Comet ML (если есть своя интеграция)
    # Пример с публичным httpbin:
    # payload = {"prompt": prompt}
    # async with aiohttp.ClientSession() as session:
    #     async with session.post("https://some-ai-image-api/generate", json=payload) as resp:
    #         data = await resp.json()
    #         image_url = data["image_url"]
    #         return image_url
    # Пока просто возвращаем ссылку-рыбу:
    return "https://placehold.co/600x400?text=AI+Image"

@router.message(Command("join"))
async def join_game(message: types.Message):
    uid = message.from_user.id
    if uid not in game_state["players"]:
        game_state["players"].append(uid)
        await message.answer("Вы в игре!")
    else:
        await message.answer("Вы уже в игре.")

@router.message(Command("new_game"))
async def new_game(message: types.Message):
    if len(game_state["players"]) < 2:
        await message.answer("Соберите хотя бы двух игроков.")
        return
    game_state["host_index"] = 0
    game_state["phase"] = "situation_choice"
    game_state["current_options"] = random.sample(situations, 3)
    host_id = game_state["players"][game_state["host_index"]]
    texts = [f'{i+1}) {x["text"]}' for i, x in enumerate(game_state["current_options"])]
    kb = [
        [types.KeyboardButton(text=str(i+1)) for i in range(len(game_state["current_options"]))]
    ]
    await message.bot.send_message(host_id, "Вы — ведущий! Выберите ситуацию:\n" + "\n".join(texts),
                                   reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, one_time_keyboard=True, resize_keyboard=True))

@router.message(lambda m: game_state["phase"] == "situation_choice" and m.from_user.id == game_state["players"][game_state["host_index"]])
async def host_chooses_situation(message: types.Message):
    try:
        idx = int(message.text.strip()) - 1
        situation = game_state["current_options"][idx]
    except:
        await message.answer("Пожалуйста, выберите номер ситуации.")
        return
    game_state["current_situation"] = situation
    game_state["phase"] = "collecting_answers"
    game_state["round_answers"] = {}

    for uid in game_state["players"]:
        if uid != message.from_user.id:
            await message.bot.send_message(uid, f"Ситуация: {situation['text']}\nОтправьте ваш ответ!")

    await message.answer("Ситуация выбрана. Ждём ответы игроков.", reply_markup=types.ReplyKeyboardRemove())

@router.message(lambda m: game_state["phase"] == "collecting_answers" and m.from_user.id != game_state["players"][game_state["host_index"]])
async def collect_answer(message: types.Message):
    uid = message.from_user.id
    if uid in game_state["round_answers"]:
        await message.answer("Вы уже отправили ответ.")
        return
    game_state["round_answers"][uid] = message.text
    await message.answer("Ответ принят!")

    if len(game_state["round_answers"]) == len(game_state["players"]) - 1:
        host_id = game_state["players"][game_state["host_index"]]
        texts = [f"{i+1}) {txt}" for i, txt in enumerate(game_state["round_answers"].values())]
        kb = [
            [types.KeyboardButton(text=str(i+1)) for i in range(len(texts))]
        ]
        await message.bot.send_message(host_id, "Все ответы получены. Выберите лучший:", 
            reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, one_time_keyboard=True, resize_keyboard=True))
        game_state["phase"] = "choose_winner"

@router.message(lambda m: game_state["phase"] == "choose_winner" and m.from_user.id == game_state["players"][game_state["host_index"]])
async def choose_winner(message: types.Message):
    try:
        idx = int(message.text.strip()) - 1
        winner_id = list(game_state["round_answers"].keys())[idx]
        answer = list(game_state["round_answers"].values())[idx]
    except:
        await message.answer("Выберите номер лучшего ответа.")
        return

    # Генерируем картинку!
    prompt = f"{game_state['current_situation']['text']} Ответ: {answer}"
    image_url = await generate_image(prompt)
    await message.answer("Лучший ответ выбран! Вот генерация картинки по ситуации и ответу:")

    # Отправляем всем участникам картинку и результат
    for uid in game_state["players"]:
        await message.bot.send_photo(uid, image_url, 
          caption=f"Ситуация: {game_state['current_situation']['text']}\nЛучший ответ: {answer}")

    # Дальше — смена ведущего и новый раунд
    game_state["host_index"] = (game_state["host_index"] + 1) % len(game_state["players"])
    game_state["phase"] = "situation_choice"
    game_state["current_options"] = random.sample(situations, 3)
    host_id = game_state["players"][game_state["host_index"]]
    texts = [f'{i+1}) {x["text"]}' for i, x in enumerate(game_state["current_options"])]
    kb = [
        [types.KeyboardButton(text=str(i+1)) for i in range(len(game_state["current_options"]))]
    ]
    await message.bot.send_message(host_id, "Теперь вы — ведущий!\nВыберите ситуацию:\n" + "\n".join(texts), 
        reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, one_time_keyboard=True, resize_keyboard=True))

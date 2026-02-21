import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

TOKEN = "TOKEN"

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

games = {}
player_room = {}
waiting_for_code = set()


# =========================
# КЛАВИАТУРЫ
# =========================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Создать игру")],
        [KeyboardButton(text="🔑 Присоединиться")],
        [KeyboardButton(text="🚪 Покинуть игру")]
    ],
    resize_keyboard=True
)


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def generate_room_code():
    while True:
        code = str(random.randint(10, 99))
        if code not in games:
            return code


def create_board():
    return [" "] * 9


def assign_symbols(game):
    """Случайное распределение ❌ и ⭕"""
    players = game["players"]
    random.shuffle(players)

    players[0]["symbol"] = "❌"
    players[1]["symbol"] = "⭕"

    game["turn"] = players[0]["id"]


def render_board(board, finished=False):
    keyboard = []

    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            index = i + j
            text = board[index] if board[index] != " " else " "
            callback = f"move_{index}" if not finished else "disabled"
            row.append(
                InlineKeyboardButton(text=text, callback_data=callback)
            )
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def check_winner(board):
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6)
    ]
    for a,b,c in wins:
        if board[a] == board[b] == board[c] != " ":
            return board[a]
    if " " not in board:
        return "draw"
    return None


async def update_board(game, text, finished=False, extra_buttons=None):
    keyboard = render_board(game["board"], finished)

    if extra_buttons:
        keyboard.inline_keyboard.append(extra_buttons)

    for player in game["players"]:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=player["id"],
                message_id=game["messages"][player["id"]],
                reply_markup=keyboard
            )
        except:
            pass


async def force_leave(user_id):
    if user_id not in player_room:
        return False

    code = player_room[user_id]
    game = games.get(code)

    if not game:
        return False

    for p in game["players"]:
        player_room.pop(p["id"], None)
        try:
            await bot.edit_message_text(
                text="Игра завершена.",
                chat_id=p["id"],
                message_id=game["messages"].get(p["id"])
            )
        except:
            pass

    del games[code]
    return True


# =========================
# START
# =========================

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Добро пожаловать в Крестики-Нолики!\n\nВыберите действие:",
        reply_markup=main_menu
    )


# =========================
# ВЫХОД
# =========================

@dp.message(F.text == "🚪 Покинуть игру")
@dp.message(Command("leave"))
async def leave_handler(message: Message):
    waiting_for_code.discard(message.from_user.id)

    success = await force_leave(message.from_user.id)

    if success:
        await message.answer("Ты покинул игру.", reply_markup=main_menu)
    else:
        await message.answer("Ты не находишься в игре.", reply_markup=main_menu)


# =========================
# СОЗДАНИЕ ИГРЫ
# =========================

@dp.message(F.text == "🎮 Создать игру")
async def new_game(message: Message):
    user_id = message.from_user.id

    if user_id in player_room:
        await message.answer("Ты уже находишься в игре.", reply_markup=main_menu)
        return

    code = generate_room_code()

    games[code] = {
        "board": create_board(),
        "players": [
            {"id": user_id, "name": message.from_user.first_name}
        ],
        "turn": None,
        "messages": {}
    }

    player_room[user_id] = code

    await message.answer(
        f"Комната создана!\n"
        f"Код комнаты: <b>{code}</b>\n\n"
        f"Ожидание второго игрока...",
        reply_markup=main_menu
    )


# =========================
# ПРИСОЕДИНЕНИЕ
# =========================

@dp.message(F.text == "🔑 Присоединиться")
async def ask_room_code(message: Message):
    waiting_for_code.add(message.from_user.id)
    await message.answer("Введите код комнаты (2 цифры):", reply_markup=main_menu)


# =========================
# ВВОД КОДА
# =========================

@dp.message(F.text)
async def handle_code_input(message: Message):
    user_id = message.from_user.id

    if user_id not in waiting_for_code:
        return

    waiting_for_code.remove(user_id)

    if user_id in player_room:
        await message.answer("Ты уже в игре.", reply_markup=main_menu)
        return

    code = message.text.strip()

    if code not in games:
        await message.answer("Комната не найдена.", reply_markup=main_menu)
        return

    game = games[code]

    if len(game["players"]) >= 2:
        await message.answer("Комната заполнена.", reply_markup=main_menu)
        return

    game["players"].append({
        "id": user_id,
        "name": message.from_user.first_name
    })

    player_room[user_id] = code

    assign_symbols(game)

    p1 = game["players"][0]
    p2 = game["players"][1]

    first_player = next(p for p in game["players"] if p["symbol"] == "❌")

    text = (
        f"Игра началась!\n\n"
        f"{p1['name']} — {p1['symbol']}\n"
        f"{p2['name']} — {p2['symbol']}\n\n"
        f"Ходит: {first_player['name']} (❌)"
    )

    keyboard = render_board(game["board"])

    for player in game["players"]:
        msg = await bot.send_message(
            player["id"],
            text,
            reply_markup=keyboard
        )
        game["messages"][player["id"]] = msg.message_id


# =========================
# ХОД
# =========================

@dp.callback_query(F.data.startswith("move_"))
async def handle_move(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in player_room:
        await callback.answer()
        return

    code = player_room[user_id]
    game = games.get(code)

    if not game or user_id != game["turn"]:
        await callback.answer("Не твой ход.")
        return

    index = int(callback.data.split("_")[1])

    if game["board"][index] != " ":
        await callback.answer("Клетка занята.")
        return

    player = next(p for p in game["players"] if p["id"] == user_id)
    game["board"][index] = player["symbol"]

    winner = check_winner(game["board"])

    if winner:
        if winner == "draw":
            text = "🤝 Ничья!"
        else:
            winner_player = next(p for p in game["players"] if p["symbol"] == winner)
            text = f"🏆 Победил {winner_player['name']} ({winner})"

        restart_button = [
            InlineKeyboardButton(text="Играть ещё раз", callback_data="restart")
        ]

        await update_board(game, text, finished=True, extra_buttons=restart_button)
        return

    other = next(p for p in game["players"] if p["id"] != user_id)
    game["turn"] = other["id"]

    text = f"Ходит: {other['name']} ({other['symbol']})"
    await update_board(game, text)

    await callback.answer()


# =========================
# РЕСТАРТ
# =========================

@dp.callback_query(F.data == "restart")
async def restart_game(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in player_room:
        return

    code = player_room[user_id]
    game = games.get(code)

    if not game:
        return

    game["board"] = create_board()

    assign_symbols(game)

    p1 = game["players"][0]
    p2 = game["players"][1]

    first_player = next(p for p in game["players"] if p["symbol"] == "❌")

    text = (
        f"Новая игра!\n\n"
        f"{p1['name']} — {p1['symbol']}\n"
        f"{p2['name']} — {p2['symbol']}\n\n"
        f"Ходит: {first_player['name']} (❌)"
    )

    await update_board(game, text)


# =========================
# ЗАПУСК
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
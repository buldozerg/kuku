import json
import asyncio
import logging
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv("TOKEN")
TON_API_KEY = os.getenv("TON_API_KEY")
CHECK_TOKEN = os.getenv("CHECK_TOKEN")
COMMAND_ADD = os.getenv("COMMAND_ADD", "addforkukuadminlong")
COMMAND_ERASE = os.getenv("COMMAND_ERASE", "eraseforkukuadminlong")
COMMAND_CHECK = os.getenv("COMMAND_CHECK", "checkforkukuadminlong")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальные переменные
user_state = {}
last_total_balance = 0
last_user_balances = {}  # Хранение предыдущих балансов пользователей

# Функции для работы с данными и балансом (не меняются)

@dp.message(Command(COMMAND_ADD))
async def add_user(message: Message):
    user_state[message.from_user.id] = 'waiting_for_nickname'
    await message.answer("Введите ваш никнейм:")


@dp.message(Command(COMMAND_ERASE))
async def erase_user(message: Message):
    user_state[message.from_user.id] = 'waiting_for_erase_nickname'
    await message.answer("Введите ник пользователя, которого удалить:")


@dp.message(Command(COMMAND_CHECK))
async def check_users(message: Message):
    data = load_data()
    users = data["users"]
    if not users:
        await message.answer("Нет пользователей для отображения.")
        return

    response = "Список пользователей:\n"
    for user in users:
        username = user["username"]
        wallet = user["wallet"]
        new_balance = await get_wallet_balance(wallet)
        change = new_balance - user["balance"]
        user["balance"] = new_balance  # Обновляем баланс
        response += f"\n🔹 {username}\n💳 {wallet}\n💰 {new_balance} ({change:+.2f})\n"

    save_data(data)
    await message.answer(response)

# Остальные функции не меняются

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))

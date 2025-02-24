import json
import asyncio
import logging
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
import os

TOKEN = os.getenv("TOKEN")
TON_API_KEY = os.getenv("TON_API_KEY")
CHECK_TOKEN = os.getenv("CHECK_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  # Получаем пароль из переменной окружения

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальные переменные
user_state = {}
last_total_balance = 0
last_user_balances = {}  # Хранение предыдущих балансов пользователей


def load_data():
    """Загружает данные из JSON-файла."""
    try:
        with open("users.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"users": []}


def save_data(data):
    """Сохраняет данные в JSON-файл."""
    with open("users.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


async def get_wallet_balance(wallet: str) -> float:
    """Получение баланса кошелька в отслеживаемых токенах через TON API"""
    url = f"https://tonapi.io/v2/accounts/{wallet}/jettons"
    headers = {"Authorization": f"Bearer {TON_API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for jetton in data.get("balances", []):
                    if jetton["jetton"]["address"] == CHECK_TOKEN:
                        return int(jetton["balance"]) / (10 ** int(jetton["jetton"]["decimals"]))
    except Exception as e:
        logging.error(f"Ошибка получения баланса: {e}")

    return 0.0  # Если токен не найден или произошла ошибка, возвращаем 0


async def check_password(message: Message):
    """Запрашивает пароль у пользователя и проверяет его."""
    if message.text != ADMIN_PASSWORD:
        await message.answer("❌ Неверный пароль.")
        return False
    return True


@dp.message(Command("add"))
async def add_user(message: Message):
    if not await check_password(message):
        return
    user_state[message.from_user.id] = 'waiting_for_nickname'
    await message.answer("Введите ваш никнейм:")


@dp.message(Command("erase"))
async def erase_user(message: Message):
    if not await check_password(message):
        return
    user_state[message.from_user.id] = 'waiting_for_erase_nickname'
    await message.answer("Введите ник пользователя, которого удалить:")


@dp.message(Command("check"))
async def check_users(message: Message):
    if not await check_password(message):
        return

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


@dp.message(Command("sum"))
async def sum_info(message: Message):
    global last_total_balance

    data = load_data()
    users = data["users"]

    count = len(users)
    total_balance = sum(user["balance"] for user in users)
    balance_change = total_balance - last_total_balance
    last_total_balance = total_balance  # Обновляем глобальный баланс

    await message.answer(
        f"👥 Количество пользователей: {count}\n"
        f"💰 Общий баланс: {total_balance}\n"
        f"📉 Изменение: {balance_change:+.2f}"
    )


@dp.message(Command("list"))
async def list_users(message: Message):
    global last_user_balances

    data = load_data()
    users = data["users"]
    if not users:
        await message.answer("Нет пользователей в базе.")
        return

    response = "📋 Список пользователей:\n\n"
    for user in users:
        username = user["username"]
        wallet = user["wallet"]

        # Получаем текущий баланс
        current_balance = await get_wallet_balance(wallet)

        # Вычисляем изменение баланса со времени последнего вызова /list
        previous_balance = last_user_balances.get(username, current_balance)
        balance_change = current_balance - previous_balance

        # Обновляем хранилище балансов
        last_user_balances[username] = current_balance

        # Формируем информацию
        response += (
            f"🔹 {username}\n"
            f"💳 Кошелёк: {wallet}\n"
            f"💰 Баланс сейчас: {current_balance}\n"
            f"📉 Изменение: {balance_change:+.2f}\n\n"
        )

    await message.answer(response)


@dp.message()
async def process_message(message: Message):
    """Обработка состояний пользователей."""
    user_id = message.from_user.id
    state = user_state.get(user_id)

    if state == 'waiting_for_nickname':
        user_state[user_id] = 'waiting_for_wallet'
        user_state[str(user_id) + '_nickname'] = message.text
        await message.answer("Теперь введите ваш TON-кошелёк:")

    elif state == 'waiting_for_wallet':
        nickname = user_state.get(str(user_id) + '_nickname')
        wallet = message.text
        token_balance = await get_wallet_balance(wallet)

        data = load_data()
        user_found = False
        for user in data["users"]:
            if user["username"] == nickname:
                user["wallet"] = wallet
                user["balance"] = token_balance
                user_found = True
                break

        if not user_found:
            data["users"].append({
                "username": nickname,
                "wallet": wallet,
                "balance": token_balance
            })

        save_data(data)
        del user_state[user_id]

        await message.answer(
            f"✅ Данные сохранены:\n"
            f"🔹 Ник: {nickname}\n"
            f"💳 Кошелёк: {wallet}\n"
            f"💰 Баланс: {token_balance}"
        )

    elif state == 'waiting_for_erase_nickname':
        username = message.text
        data = load_data()
        data["users"] = [user for user in data["users"] if user["username"] != username]
        save_data(data)
        del user_state[user_id]

        await message.answer(f"❌ Пользователь {username} удалён из базы")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))

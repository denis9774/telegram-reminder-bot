import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler


TOKEN = "8754227471:AAG9oE0z9XX-SGKIFai0UAChCEDThuexnkQ"


bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


user_data = {}


# --- БАЗА ---
async def init_db():
    async with aiosqlite.connect("reminders.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            text TEXT,
            time TEXT
        )
        """)
        await db.commit()


async def add_reminder(user_id, text, time):
    async with aiosqlite.connect("reminders.db") as db:
        await db.execute(
            "INSERT INTO reminders (user_id, text, time) VALUES (?, ?, ?)",
            (user_id, text, time)
        )
        await db.commit()


# --- КНОПКИ ---
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать напоминание", callback_data="create")
    return kb.as_markup()


# --- СТАРТ ---
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Я бот-напоминалка ⏰", reply_markup=main_menu())


# --- СОЗДАНИЕ ---
@dp.callback_query(F.data == "create")
async def create_reminder(callback: CallbackQuery):
    user_data[callback.from_user.id] = {}
    await callback.message.answer("Напиши текст напоминания:")
    await callback.answer()


# --- ТЕКСТ ---
@dp.message()
async def get_text(message: Message):
    if message.from_user.id in user_data and "text" not in user_data[message.from_user.id]:
        user_data[message.from_user.id]["text"] = message.text


        kb = InlineKeyboardBuilder()
        kb.button(text="Сегодня", callback_data="today")
        kb.button(text="Завтра", callback_data="tomorrow")


        await message.answer("Выбери дату:", reply_markup=kb.as_markup())


# --- ДАТА ---
@dp.callback_query(F.data.in_(["today", "tomorrow"]))
async def set_date(callback: CallbackQuery):
    now = datetime.now()


    if callback.data == "today":
        date = now.date()
    else:
        date = (now.replace(day=now.day+1)).date()


    user_data[callback.from_user.id]["date"] = str(date)


    await callback.message.answer("Теперь введи время (например 14:30):")
    await callback.answer()


# --- ВРЕМЯ ---
@dp.message()
async def get_time(message: Message):
    data = user_data.get(message.from_user.id)


    if data and "date" in data and "time" not in data:
        try:
            time = message.text
            full_time = f"{data['date']} {time}"
            dt = datetime.strptime(full_time, "%Y-%m-%d %H:%M")


            user_data[message.from_user.id]["time"] = dt


            await add_reminder(message.from_user.id, data["text"], str(dt))


            scheduler.add_job(send_reminder, 'date', run_date=dt,
                              args=[message.from_user.id, data["text"]])


            await message.answer("✅ Напоминание сохранено!", reply_markup=main_menu())


            user_data.pop(message.from_user.id)


        except:
            await message.answer("❌ Неправильный формат времени. Напиши так: 14:30")


# --- ОТПРАВКА ---
async def send_reminder(user_id, text):
    await bot.send_message(user_id, f"⏰ Напоминание: {text}")


# --- ЗАПУСК ---
async def main():
    await init_db()
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

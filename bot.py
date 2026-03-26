import asyncio
import aiosqlite
from datetime import datetime
from calendar import monthcalendar
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# --- Токен ---
TOKEN = os.getenv("TOKEN")
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

async def load_reminders():
    async with aiosqlite.connect("reminders.db") as db:
        async with db.execute("SELECT user_id, text, time FROM reminders") as cursor:
            rows = await cursor.fetchall()
            for user_id, text, time in rows:
                dt = datetime.fromisoformat(time)
                if dt > datetime.now():
                    scheduler.add_job(
                        send_reminder,
                        'date',
                        run_date=dt,
                        args=[user_id, text]
                    )

# --- КНОПКИ ---
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать напоминание", callback_data="create")
    return kb.as_markup()

def create_calendar(year, month):
    kb = InlineKeyboardBuilder()
    for week in monthcalendar(year, month):
        for day in week:
            if day == 0:
                kb.button(text=" ", callback_data="ignore")
            else:
                kb.button(text=str(day), callback_data=f"day_{year}_{month}_{day}")
    kb.adjust(7)
    return kb.as_markup()

def time_keyboard():
    kb = InlineKeyboardBuilder()
    times = ["09:00", "12:00", "15:00", "18:00", "21:00"]
    for t in times:
        kb.button(text=t, callback_data=f"time_{t}")
    kb.adjust(2)
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
        now = datetime.now()
        await message.answer("Выбери дату:", reply_markup=create_calendar(now.year, now.month))

# --- ДАТА ---
@dp.callback_query(F.data.startswith("day_"))
async def pick_day(callback: CallbackQuery):
    _, year, month, day = callback.data.split("_")
    user_data[callback.from_user.id]["date"] = f"{year}-{month}-{day}"
    await callback.message.answer("Теперь выбери время:", reply_markup=time_keyboard())
    await callback.answer()

# --- ВРЕМЯ ---
@dp.callback_query(F.data.startswith("time_"))
async def pick_time(callback: CallbackQuery):
    time = callback.data.split("_")[1]
    data = user_data[callback.from_user.id]
    full_time = f"{data['date']} {time}"
    dt = datetime.strptime(full_time, "%Y-%m-%d %H:%M")
    user_data[callback.from_user.id]["time"] = dt
    await add_reminder(callback.from_user.id, data["text"], str(dt))
    scheduler.add_job(send_reminder, 'date', run_date=dt, args=[callback.from_user.id, data["text"]])
    await callback.message.answer("✅ Напоминание создано!", reply_markup=main_menu())
    user_data.pop(callback.from_user.id)
    await callback.answer()

# --- ОТПРАВКА ---
async def send_reminder(user_id, text):
    await bot.send_message(user_id, f"⏰ Напоминание: {text}")

# --- WEBHOOK для Railway ---
WEBHOOK_HOST = os.getenv("RAILWAY_STATIC_URL")  # URL проекта Railway
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    await init_db()
    await load_reminders()
    scheduler.start()

async def on_shutdown():
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

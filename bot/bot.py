import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=API_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

from bot.handlers.start import router as start_router
from bot.handlers.files import router as files_router
from bot.handlers.stop import router as stop_router

dp.include_router(start_router)
dp.include_router(files_router)
dp.include_router(stop_router)


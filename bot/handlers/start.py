from aiogram import types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.bot import dp
from bot.states.bot_states import BotStates
router = Router()

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):

    await message.reply(
        "👋 Привет! Загрузи первый .txt файл аккаунтов"
    )

    await state.set_state(
        BotStates.waiting_first_file
    )
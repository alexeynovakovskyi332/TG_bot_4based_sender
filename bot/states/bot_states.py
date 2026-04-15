from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):

    waiting_first_file = State()

    waiting_second_file = State()
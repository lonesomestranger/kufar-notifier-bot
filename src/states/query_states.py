from aiogram.fsm.state import State, StatesGroup


class QuerySettings(StatesGroup):
    waiting_for_price = State()
    waiting_for_limit = State()
    waiting_for_city = State()


class AddQuery(StatesGroup):
    waiting_for_text = State()
    waiting_for_city = State()

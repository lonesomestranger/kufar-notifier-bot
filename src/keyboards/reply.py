from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def create_main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Меню")]], resize_keyboard=True
    )

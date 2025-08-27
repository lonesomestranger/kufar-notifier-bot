from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src import config
from src.utils import data_manager

router = Router()


@router.message(Command("adminhelp"))
async def send_admin_help(message: Message):
    help_text = (
        "<b>Админ-панель</b>\n\n"
        "/adduser &lt;user_id&gt; - Добавить пользователя\n"
        "/deluser &lt;user_id&gt; - Удалить пользователя\n"
        "/listusers - Список пользователей"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("adduser"))
async def add_user(message: Message, command: CommandObject):
    try:
        user_id = int(command.args)
        users = data_manager.load_users()
        if user_id not in users:
            users.append(user_id)
            data_manager.save_users(users)
            await message.answer(f"Пользователь {user_id} добавлен.")
        else:
            await message.answer(f"Пользователь {user_id} уже существует.")
    except (ValueError, TypeError):
        await message.answer("Неверный формат. Используйте: /adduser <user_id>")


@router.message(Command("deluser"))
async def del_user(message: Message, command: CommandObject):
    try:
        user_id = int(command.args)
        users = data_manager.load_users()
        if user_id in users:
            users.remove(user_id)
            data_manager.save_users(users)
            await message.answer(f"Пользователь {user_id} удален.")
        else:
            await message.answer(f"Пользователь {user_id} не найден.")
    except (ValueError, TypeError):
        await message.answer("Неверный формат. Используйте: /deluser <user_id>")


@router.message(Command("listusers"))
async def list_users(message: Message):
    users = data_manager.load_users()
    admins = config.ADMIN_IDS
    if not users:
        await message.answer("Список пользователей пуст.")
        return

    user_lines = []
    for user_id in users:
        label = " (админ)" if user_id in admins else ""
        user_lines.append(f"• <code>{user_id}</code>{label}")

    await message.answer(
        "<b>Список пользователей:</b>\n" + "\n".join(user_lines),
        parse_mode=ParseMode.HTML,
    )

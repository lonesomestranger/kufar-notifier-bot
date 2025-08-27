from aiogram.filters import BaseFilter
from aiogram.types import Message

from src import config
from src.utils import data_manager


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in config.ADMIN_IDS


class IsUser(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in data_manager.load_users()

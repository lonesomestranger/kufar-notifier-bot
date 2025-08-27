from aiogram import Router

from src.filters.access_filters import IsAdmin, IsUser

from . import admin, user


def setup_routers() -> Router:
    main_router = Router()

    admin.router.message.filter(IsAdmin())
    main_router.include_router(admin.router)

    user.router.message.filter(IsUser())
    user.router.callback_query.filter(IsUser())
    main_router.include_router(user.router)

    return main_router

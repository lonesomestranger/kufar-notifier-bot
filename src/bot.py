import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from curl_cffi.requests import AsyncSession

from src import config
from src.handlers import setup_routers
from src.utils import data_manager, kufar_api


async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Перезапустить бота / Показать меню"),
    ]
    admin_commands = user_commands + [
        BotCommand(command="adminhelp", description="Команды администратора"),
    ]
    await bot.set_my_commands(admin_commands)


async def polling_task(bot: Bot):
    bot_start_time_utc = datetime.now(timezone.utc)
    logging.info(
        f"Бот запущен в {bot_start_time_utc}. Объявления до этого времени будут игнорироваться."
    )
    cached_ad_ids = data_manager.load_cached_ads()
    async with AsyncSession() as session:
        while True:
            logging.info("Запуск цикла проверки...")
            all_queries_by_user = data_manager.load_queries()
            if not all_queries_by_user:
                logging.info("Нет активных запросов. Пропускаем цикл.")
                await asyncio.sleep(config.DELAY_MAIN_LOOP)
                continue
            query_to_users_map = defaultdict(list)
            unique_queries = set()
            for user_id, user_queries in all_queries_by_user.items():
                for query in user_queries:
                    frozen_query = frozenset(query.items())
                    unique_queries.add(frozen_query)
                    query_to_users_map[frozen_query].append(int(user_id))
            for frozen_query in unique_queries:
                query_params = dict(frozen_query)
                new_ads = await kufar_api.get_new_ads(session, query_params)
                for ad in reversed(new_ads):
                    ad_id = ad.get("ad_id")
                    ad_time_utc = kufar_api.get_ad_timestamp(ad)
                    if (
                        ad_id not in cached_ad_ids
                        and ad_time_utc
                        and ad_time_utc > bot_start_time_utc
                    ):
                        cached_ad_ids.add(ad_id)
                        data_manager.save_cached_ads(cached_ad_ids)
                        caption = kufar_api.format_ad_message(ad)
                        photo_url = kufar_api.get_photo_url(ad)
                        users_to_notify = query_to_users_map[frozen_query]
                        for user_id in users_to_notify:
                            try:
                                if photo_url:
                                    await bot.send_photo(
                                        user_id,
                                        photo=photo_url,
                                        caption=caption,
                                        parse_mode=ParseMode.HTML,
                                    )
                                else:
                                    await bot.send_message(
                                        user_id,
                                        text=caption,
                                        parse_mode=ParseMode.HTML,
                                        disable_web_page_preview=True,
                                    )
                            except Exception as e:
                                logging.error(
                                    f"Не удалось отправить уведомление пользователю {user_id}: {e}"
                                )
                        await asyncio.sleep(1)
                await asyncio.sleep(config.DELAY_BETWEEN_QUERIES)
            logging.info(f"Цикл завершен. Ожидание {config.DELAY_MAIN_LOOP} секунд.")
            await asyncio.sleep(config.DELAY_MAIN_LOOP)


async def main():
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    main_router = setup_routers()
    dp.include_router(main_router)
    await set_bot_commands(bot)
    users = data_manager.load_users()
    users_updated = False
    for admin_id in config.ADMIN_IDS:
        if admin_id not in users:
            users.append(admin_id)
            logging.info(f"Администратор {admin_id} добавлен в список пользователей.")
            users_updated = True
    if users_updated:
        data_manager.save_users(users)
    loop = asyncio.get_event_loop()
    loop.create_task(polling_task(bot))
    await dp.start_polling(bot)

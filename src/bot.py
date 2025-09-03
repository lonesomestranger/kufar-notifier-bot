import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

from src import config
from src.handlers import setup_routers
from src.keyboards import inline as keyboards
from src.logging_config import setup_logging
from src.utils import data_manager, kufar_api

load_dotenv()


def get_ad_location(ad: dict) -> str:
    region, area = "", ""
    for param in ad.get("ad_parameters", []):
        if param.get("p") == "region":
            region = param.get("vl")
        if param.get("p") == "area":
            area = param.get("vl")
    return f"{region} / {area}"


async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Перезапустить бота / Показать меню"),
    ]
    admin_commands = user_commands + [
        BotCommand(command="adminhelp", description="Команды администратора"),
    ]
    await bot.set_my_commands(admin_commands)


async def polling_task(bot: Bot):
    logging.info("Запуск задачи polling_task...")
    cached_ad_ids = data_manager.load_cached_ads()
    is_first_run = True
    API_DELAY_WARNING_THRESHOLD = os.getenv("API_DELAY_WARNING_THRESHOLD", 240)

    async with AsyncSession() as session:
        while True:
            cycle_start_time = time.monotonic()

            if is_first_run:
                logging.info("Первый запуск: начинаем прогрев кеша...")
                all_queries_by_user = data_manager.load_queries()
                if all_queries_by_user:
                    unique_queries = set()
                    for user_queries in all_queries_by_user.values():
                        for query in user_queries:
                            unique_queries.add(frozenset(query.items()))

                    logging.info(
                        f"Найдено {len(unique_queries)} уникальных запросов для прогрева."
                    )

                    initial_ids_to_cache = set()
                    for frozen_query in unique_queries:
                        query_params = dict(frozen_query)
                        ads = await kufar_api.get_new_ads(session, query_params)
                        for ad in ads:
                            if ad_id := ad.get("ad_id"):
                                initial_ids_to_cache.add(ad_id)
                        await asyncio.sleep(1)

                    cached_ad_ids.update(initial_ids_to_cache)
                    data_manager.save_cached_ads(cached_ad_ids)
                    logging.info(
                        f"Прогрев кеша завершен. В кеше {len(cached_ad_ids)} ID. Начинаем мониторинг."
                    )
                else:
                    logging.info("Нет активных запросов, прогрев кеша пропущен.")

                is_first_run = False
                continue

            cached_ad_ids = data_manager.load_cached_ads()

            logging.debug("Запуск цикла проверки...")
            all_queries_by_user = data_manager.load_queries()
            if not all_queries_by_user:
                logging.debug("Нет активных запросов. Пропускаем цикл.")
                await asyncio.sleep(config.DELAY_MAIN_LOOP)
                continue

            grouping_start_time = time.monotonic()
            query_to_users_map = defaultdict(list)
            unique_queries = set()
            for user_id, user_queries in all_queries_by_user.items():
                for query in user_queries:
                    frozen_query = frozenset(query.items())
                    unique_queries.add(frozen_query)
                    query_to_users_map[frozen_query].append(int(user_id))
            logging.debug(
                f"[TIMER] Группировка {len(unique_queries)} запросов заняла: {time.monotonic() - grouping_start_time:.4f} сек."
            )

            processing_start_time = time.monotonic()
            newly_cached_ids_in_cycle = set()
            for i, frozen_query in enumerate(unique_queries, 1):
                query_check_start_time = time.monotonic()
                query_params = dict(frozen_query)
                new_ads = await kufar_api.get_new_ads(session, query_params)

                for ad in reversed(new_ads):
                    ad_id = ad.get("ad_id")
                    if ad_id not in cached_ad_ids:
                        user_city_name = query_params.get("city", "Все города")

                        if user_city_name != "Все города":
                            ad_location = get_ad_location(ad)
                            if user_city_name not in ad_location:
                                continue

                        discovery_time_utc = datetime.now(timezone.utc)
                        ad_time_utc = kufar_api.get_ad_timestamp(ad)

                        delay_seconds = -1
                        if ad_time_utc:
                            delay = discovery_time_utc - ad_time_utc
                            delay_seconds = delay.total_seconds()

                        ad_subject = ad.get("subject", "Без заголовка")
                        logging.debug(
                            f'Обнаружено: "{ad_subject}" (ID: {ad_id}) | Задержка API: {delay_seconds:.2f} сек.'
                        )

                        if delay_seconds > API_DELAY_WARNING_THRESHOLD:
                            logging.warning(
                                f"Высокая задержка API Kufar: {delay_seconds:.2f} сек!\n"
                                f'  - Объявление: "{ad_subject}" (ID: {ad_id})\n'
                                f"  - Время Kufar: {ad_time_utc.isoformat() if ad_time_utc else 'N/A'}\n"
                                f"  - Время обнаружения: {discovery_time_utc.isoformat()}"
                            )

                        extended_details = await kufar_api.get_extended_ad_details(
                            session, ad.get("ad_link"), ad_id
                        )

                        cached_ad_ids.add(ad_id)
                        newly_cached_ids_in_cycle.add(ad_id)
                        caption = kufar_api.format_ad_message(ad, extended_details)
                        photo_url = kufar_api.get_photo_url(ad)

                        keyboard = keyboards.create_ad_link_keyboard(ad.get("ad_link"))

                        users_to_notify = query_to_users_map[frozen_query]
                        for user_id in users_to_notify:
                            try:
                                if photo_url:
                                    await bot.send_photo(
                                        user_id,
                                        photo=photo_url,
                                        caption=caption,
                                        parse_mode=ParseMode.HTML,
                                        reply_markup=keyboard,
                                    )
                                else:
                                    await bot.send_message(
                                        user_id,
                                        text=caption,
                                        parse_mode=ParseMode.HTML,
                                        disable_web_page_preview=True,
                                        reply_markup=keyboard,
                                    )
                            except Exception as e:
                                logging.error(
                                    f"Не удалось отправить уведомление пользователю {user_id}: {e}"
                                )
                        await asyncio.sleep(0.5)

                logging.debug(
                    f"[TIMER] Проверка запроса {i}/{len(unique_queries)} заняла: {time.monotonic() - query_check_start_time:.4f} сек."
                )
                await asyncio.sleep(config.DELAY_BETWEEN_QUERIES)

            logging.debug(
                f"[TIMER] Вся обработка и отправка заняла: {time.monotonic() - processing_start_time:.4f} сек."
            )

            if newly_cached_ids_in_cycle:
                save_start_time = time.monotonic()
                data_manager.save_cached_ads(cached_ad_ids)
                logging.debug(
                    f"Сохранено {len(newly_cached_ids_in_cycle)} новых ID в кеш."
                )
                logging.debug(
                    f"[TIMER] Сохранение кеша заняло: {time.monotonic() - save_start_time:.4f} сек."
                )

            cycle_duration = time.monotonic() - cycle_start_time
            logging.debug(
                f"[TIMER] Полное время цикла проверки: {cycle_duration:.4f} сек."
            )
            logging.debug(f"Цикл завершен. Ожидание {config.DELAY_MAIN_LOOP} секунд.")
            await asyncio.sleep(config.DELAY_MAIN_LOOP)


async def main():
    setup_logging()
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

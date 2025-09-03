import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from curl_cffi.requests import AsyncSession

from src.callback_data.factories import (
    CityCallbackFactory,
    QueryActionCallbackFactory,
    QueryCallbackFactory,
)
from src.keyboards import inline as keyboards
from src.keyboards import reply as reply_keyboards
from src.states.query_states import AddQuery, QuerySettings
from src.utils import data_manager, kufar_api

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать! Нажмите кнопку «Меню», чтобы начать.",
        reply_markup=reply_keyboards.create_main_menu_reply_keyboard(),
    )


@router.message(F.text == "Меню")
async def show_main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню:", reply_markup=keyboards.create_main_menu_keyboard()
    )


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:", reply_markup=keyboards.create_main_menu_keyboard()
    )


@router.callback_query(F.data == "my_queries")
async def my_queries_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user_queries = data_manager.load_queries().get(user_id, [])
    if not user_queries:
        await callback.answer(
            "У вас еще нет запросов. Сначала добавьте один.", show_alert=True
        )
        return
    await callback.message.edit_text(
        "Ваши поисковые запросы:",
        reply_markup=keyboards.create_queries_keyboard(user_queries),
    )


@router.callback_query(F.data == "add_query")
async def add_query_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddQuery.waiting_for_text)
    await callback.message.edit_text("Введите текст для нового поискового запроса:")


@router.message(AddQuery.waiting_for_text)
async def process_add_query_text(message: Message, state: FSMContext):
    await state.update_data(query_text=message.text)
    await state.set_state(AddQuery.waiting_for_city)
    await message.answer(
        "Отлично! Теперь выберите город для поиска:",
        reply_markup=keyboards.create_city_selection_keyboard(),
    )


@router.callback_query(AddQuery.waiting_for_city, CityCallbackFactory.filter())
async def process_add_query_city(
    callback: CallbackQuery, callback_data: CityCallbackFactory, state: FSMContext
):
    data = await state.get_data()
    query_text = data["query_text"]
    city_name = callback_data.city_name

    query_data = {"query": query_text, "city": city_name}

    logging.info(f"Добавлен новый запрос {query_data}. Прогреваем для него кеш...")
    try:
        async with AsyncSession() as session:
            initial_ads = await kufar_api.get_new_ads(session, query_data)
            if initial_ads:
                initial_ids = {ad.get("ad_id") for ad in initial_ads if ad.get("ad_id")}
                cached_ads = data_manager.load_cached_ads()
                cached_ads.update(initial_ids)
                data_manager.save_cached_ads(cached_ads)
                logging.info(
                    f"Кеш для нового запроса прогрет. Добавлено {len(initial_ids)} ID."
                )
    except Exception as e:
        logging.error(f"Не удалось прогреть кеш для нового запроса: {e}")

    user_id = str(callback.from_user.id)
    all_queries = data_manager.load_queries()
    user_queries = all_queries.get(user_id, [])
    user_queries.append(query_data)
    all_queries[user_id] = user_queries
    data_manager.save_queries(all_queries)

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"Запрос «{query_text}» для города «{city_name}» успешно добавлен."
    )
    await show_main_menu(callback.message, state)


@router.callback_query(QueryCallbackFactory.filter())
async def manage_query(callback: CallbackQuery, callback_data: QueryCallbackFactory):
    q_index = callback_data.query_index
    user_id = str(callback.from_user.id)
    user_queries = data_manager.load_queries().get(user_id, [])
    if 0 <= q_index < len(user_queries):
        query = user_queries[q_index]
        text = keyboards.format_query_details(query)
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.create_manage_query_keyboard(q_index),
        )
    else:
        await callback.answer("Запрос не найден.", show_alert=True)
        await my_queries_callback(callback)


@router.callback_query(QueryActionCallbackFactory.filter(F.action == "delete_query"))
async def delete_query_action(
    callback: CallbackQuery, callback_data: QueryActionCallbackFactory
):
    q_index = callback_data.query_index
    user_id = str(callback.from_user.id)
    all_queries = data_manager.load_queries()
    user_queries = all_queries.get(user_id, [])
    if 0 <= q_index < len(user_queries):
        removed = user_queries.pop(q_index)
        all_queries[user_id] = user_queries
        if not user_queries:
            del all_queries[user_id]
        data_manager.save_queries(all_queries)
        await callback.answer(f"Запрос «{removed['query']}» удален.")
        await my_queries_callback(callback)
    else:
        await callback.answer("Запрос не найден.", show_alert=True)


@router.callback_query(QueryActionCallbackFactory.filter(F.action == "toggle_search"))
async def toggle_search_action(
    callback: CallbackQuery, callback_data: QueryActionCallbackFactory
):
    q_index = callback_data.query_index
    user_id = str(callback.from_user.id)
    all_queries = data_manager.load_queries()
    user_queries = all_queries.get(user_id, [])
    if 0 <= q_index < len(user_queries):
        user_queries[q_index]["only_title_search"] = not user_queries[q_index].get(
            "only_title_search", False
        )
        all_queries[user_id] = user_queries
        data_manager.save_queries(all_queries)
        await callback.answer("Настройка поиска в заголовках изменена.")
        await manage_query(callback, QueryCallbackFactory(query_index=q_index))
    else:
        await callback.answer("Запрос не найден.", show_alert=True)


@router.callback_query(
    QueryActionCallbackFactory.filter(
        F.action.in_({"set_price", "set_limit", "set_city"})
    )
)
async def set_parameter_action(
    callback: CallbackQuery,
    callback_data: QueryActionCallbackFactory,
    state: FSMContext,
):
    action, q_index = callback_data.action, callback_data.query_index
    await state.update_data(
        query_index=q_index, original_message_id=callback.message.message_id
    )
    if action == "set_price":
        await state.set_state(QuerySettings.waiting_for_price)
        await callback.message.edit_text(
            "Введите мин. и макс. цену через пробел (например, `100 500`).\nОтправьте `0 0` для сброса."
        )
    elif action == "set_limit":
        await state.set_state(QuerySettings.waiting_for_limit)
        await callback.message.edit_text(
            "Введите макс. количество объявлений (например, `5`)."
        )
    elif action == "set_city":
        await state.set_state(QuerySettings.waiting_for_city)
        await callback.message.edit_text(
            "Выберите новый город для этого запроса:",
            reply_markup=keyboards.create_city_selection_keyboard(),
        )


@router.callback_query(QuerySettings.waiting_for_city, CityCallbackFactory.filter())
async def process_edit_query_city(
    callback: CallbackQuery, callback_data: CityCallbackFactory, state: FSMContext
):
    data = await state.get_data()
    q_index = data["query_index"]
    city_name = callback_data.city_name

    user_id = str(callback.from_user.id)
    all_queries = data_manager.load_queries()
    user_queries = all_queries.get(user_id, [])

    if 0 <= q_index < len(user_queries):
        user_queries[q_index]["city"] = city_name
        all_queries[user_id] = user_queries
        data_manager.save_queries(all_queries)
        await callback.answer(f"Город изменен на «{city_name}».")

    await state.clear()
    await manage_query(callback, QueryCallbackFactory(query_index=q_index))


@router.message(QuerySettings.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    data = await state.get_data()
    q_index, original_message_id = data["query_index"], data["original_message_id"]
    try:
        min_price, max_price = map(int, message.text.split())
        user_id = str(message.from_user.id)
        all_queries = data_manager.load_queries()
        user_queries = all_queries.get(user_id, [])
        if 0 <= q_index < len(user_queries):
            if min_price == 0 and max_price == 0:
                user_queries[q_index].pop("price_min", None)
                user_queries[q_index].pop("price_max", None)
            else:
                (
                    user_queries[q_index]["price_min"],
                    user_queries[q_index]["price_max"],
                ) = min_price, max_price
            all_queries[user_id] = user_queries
            data_manager.save_queries(all_queries)
            await message.delete()
            await state.clear()
            query = user_queries[q_index]
            text = keyboards.format_query_details(query)
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=original_message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.create_manage_query_keyboard(q_index),
            )
    except ValueError:
        await message.answer("Неверный формат. Введите два числа через пробел.")


@router.message(QuerySettings.waiting_for_limit)
async def process_limit(message: Message, state: FSMContext):
    data = await state.get_data()
    q_index, original_message_id = data["query_index"], data["original_message_id"]
    try:
        limit = int(message.text)
        user_id = str(message.from_user.id)
        all_queries = data_manager.load_queries()
        user_queries = all_queries.get(user_id, [])
        if 0 <= q_index < len(user_queries):
            user_queries[q_index]["limit"] = limit
            all_queries[user_id] = user_queries
            data_manager.save_queries(all_queries)
            await message.delete()
            await state.clear()
            query = user_queries[q_index]
            text = keyboards.format_query_details(query)
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=original_message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.create_manage_query_keyboard(q_index),
            )
    except ValueError:
        await message.answer("Неверный формат. Введите одно число.")

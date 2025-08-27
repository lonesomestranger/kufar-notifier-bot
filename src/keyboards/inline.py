from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.callback_data.factories import QueryActionCallbackFactory, QueryCallbackFactory


def create_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Мои запросы", callback_data="my_queries")
    builder.button(text="➕ Добавить запрос", callback_data="add_query")
    builder.adjust(1)
    return builder.as_markup()


def create_queries_keyboard(user_queries: list):
    builder = InlineKeyboardBuilder()
    for i, query in enumerate(user_queries):
        builder.button(
            text=f"⚙️ {query.get('query')}",
            callback_data=QueryCallbackFactory(query_index=i),
        )
    builder.button(text="« Назад в меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def format_query_details(query: dict) -> str:
    details = [f'<b>Запрос:</b> "{query.get("query")}"']
    if "price_min" in query or "price_max" in query:
        p_min, p_max = query.get("price_min", "..."), query.get("price_max", "...")
        details.append(f"<b>Цена:</b> от {p_min} до {p_max} BYN")
    if "limit" in query:
        details.append(f"<b>Лимит:</b> {query.get('limit')} объявлений")
    if query.get("only_title_search"):
        details.append("<b>Поиск:</b> только в заголовках")
    return "\n".join(details)


def create_manage_query_keyboard(query_index: int):
    builder = InlineKeyboardBuilder()
    actions = {
        "Установить цену": "set_price",
        "Установить лимит": "set_limit",
        "Поиск в заголовках": "toggle_search",
        "❌ Удалить запрос": "delete_query",
    }
    for text, action in actions.items():
        builder.button(
            text=text,
            callback_data=QueryActionCallbackFactory(
                action=action, query_index=query_index
            ),
        )
    builder.button(text="« Назад к списку", callback_data="my_queries")
    builder.adjust(2, 1, 1)
    return builder.as_markup()

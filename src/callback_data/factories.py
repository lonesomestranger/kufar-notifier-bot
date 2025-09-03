from aiogram.filters.callback_data import CallbackData


class QueryCallbackFactory(CallbackData, prefix="query"):
    query_index: int


class QueryActionCallbackFactory(CallbackData, prefix="query_action"):
    action: str
    query_index: int


class CityCallbackFactory(CallbackData, prefix="city"):
    city_name: str

import logging
from datetime import datetime, timedelta

from curl_cffi.requests import AsyncSession

KUFAR_API_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"


def get_photo_url(ad: dict) -> str | None:
    images = ad.get("images")
    if not images:
        return None
    if images[0].get("media_storage") == "rms":
        path = images[0].get("path")
        return f"https://rms.kufar.by/v1/gallery/{path}"
    return None


def get_ad_timestamp(ad: dict) -> datetime | None:
    list_time = ad.get("list_time")
    if list_time:
        try:
            return datetime.fromisoformat(list_time.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def format_ad_message(ad: dict) -> str:
    title = ad.get("subject", "Без заголовка")
    link = ad.get("ad_link")

    price_byn, price_usd = ad.get("price_byn", "0"), ad.get("price_usd", "0")
    try:
        price_str = f"{int(price_byn) // 100} BYN / {int(price_usd) // 100}$"
    except (ValueError, TypeError):
        price_str = "Цена не указана"

    date_str = ""
    dt_object_utc = get_ad_timestamp(ad)
    if dt_object_utc:
        local_dt = dt_object_utc + timedelta(hours=3)
        date_str = local_dt.strftime("%d.%m.%Y в %H:%M:%S")

    region, area = "", ""
    for param in ad.get("ad_parameters", []):
        if param.get("p") == "region":
            region = param.get("vl")
        if param.get("p") == "area":
            area = param.get("vl")
    location_str = " / ".join(part for part in (region, area) if part)

    description = ad.get("body")

    message_parts = [
        f"<b><a href='{link}'>{title}</a></b>",
        f"<b>Цена:</b> {price_str}",
    ]
    if location_str:
        message_parts.append(f"<b>Город:</b> {location_str}")
    if date_str:
        message_parts.append(f"<b>Дата:</b> {date_str}")
    if description:
        safe_description = description.replace("<", "&lt;").replace(">", "&gt;")
        message_parts.append(f"\n{safe_description}")

    return "\n".join(message_parts)


async def get_new_ads(session: AsyncSession, query_params: dict):
    try:
        params = query_params.copy()
        params["size"] = params.pop("limit", 10)
        if params.get("only_title_search"):
            params["ot"] = 1
        params.pop("only_title_search", None)
        params.setdefault("lang", "ru")
        params.setdefault("sort", "lst.d")

        logging.info(f"Отправка запроса на {KUFAR_API_URL} с параметрами: {params}")
        response = await session.get(
            KUFAR_API_URL, params=params, impersonate="chrome110"
        )
        response.raise_for_status()
        return response.json().get("ads", [])
    except Exception as e:
        logging.error(f"Ошибка при запросе к Kufar API: {e}")
        return []

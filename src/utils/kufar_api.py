import logging
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src import config

KUFAR_API_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"


async def get_extended_ad_details(
    session: AsyncSession, ad_link: str, ad_id: str
) -> dict:
    details = {
        "description": None,
        "seller_name": None,
        "seller_ads_count": None,
        "seller_rating": None,
        "phone_number": None,
    }

    try:
        response = await session.get(ad_link, impersonate="chrome110")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        description_block = soup.find("div", attrs={"data-name": "description-block"})
        if description_block:
            description_text = description_block.get_text(strip=True, separator="\n")
            if description_text.startswith("Описание"):
                description_text = description_text[len("Описание") :].strip()
            details["description"] = description_text
            logging.info(f"HTML-парсер: Описание для {ad_id} найдено.")

        seller_block = soup.find("div", attrs={"data-name": "seller-block"})
        if seller_block:
            seller_name_tag = seller_block.find("h5")
            if seller_name_tag:
                details["seller_name"] = seller_name_tag.get_text(strip=True)
                logging.info(
                    f"HTML-парсер: Имя продавца '{details['seller_name']}' найдено."
                )

            ads_count_p = seller_block.find(
                lambda tag: tag.name == "p" and "Объявлений:" in tag.text
            )
            if ads_count_p:
                match = re.search(r"Объявлений:\s*(\d+)", ads_count_p.text)
                if match:
                    details["seller_ads_count"] = int(match.group(1))
                    logging.info(
                        f"HTML-парсер: Кол-во объявлений '{details['seller_ads_count']}' найдено."
                    )

        if config.KUFAR_BEARER_TOKEN:
            phone_url = f"https://api.kufar.by/search-api/v2/item/{ad_id}/phone"
            headers = {
                "Authorization": f"Bearer {config.KUFAR_BEARER_TOKEN}",
                "Origin": "https://www.kufar.by",
                "Referer": ad_link,
            }
            phone_response = await session.get(
                phone_url, headers=headers, impersonate="chrome110"
            )
            if phone_response.status_code == 200:
                phone_data = phone_response.json()
                details["phone_number"] = phone_data.get("phone")

    except Exception as e:
        logging.error(
            f"Критическая ошибка при парсинге страницы объявления {ad_link}: {e}"
        )

    return details


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


def format_ad_message(ad: dict, extended_details: dict) -> str:
    MAX_LENGTH = 1024

    title = ad.get("subject", "Без заголовка")

    try:
        price_byn_val = int(ad.get("price_byn", "0"))
        price_usd_val = int(ad.get("price_usd", "0"))

        if price_byn_val == 0:
            price_str = "договорная"
        else:
            price_str = f"{price_byn_val // 100} BYN / {price_usd_val // 100}$"
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

    message_parts = [
        f"<b>{title}</b>",
        f"<b>Цена:</b> {price_str}",
    ]
    if location_str:
        message_parts.append(f"📍 <b>Город:</b> {location_str}")
    if date_str:
        message_parts.append(f"📅 <b>Дата:</b> {date_str}")

    seller_info_parts = []
    if name := extended_details.get("seller_name"):
        seller_info_parts.append(name)
    if ads_count := extended_details.get("seller_ads_count"):
        seller_info_parts.append(f"({ads_count} объявл.)")

    if seller_info_parts:
        message_parts.append(f"👤 <b>Продавец:</b> {' '.join(seller_info_parts)}")

    if phone := extended_details.get("phone_number"):
        message_parts.append(f"📞 <b>Телефон:</b> <code>{phone}</code>")

    header_text = "\n".join(message_parts)

    if description := extended_details.get("description"):
        safe_description = description.replace("<", "&lt;").replace(">", "&gt;")

        description_title = "\n\n📋 <b>Описание:</b>\n"

        remaining_length = MAX_LENGTH - len(header_text) - len(description_title)

        if len(safe_description) > remaining_length:
            truncated_desc = safe_description[: remaining_length - 3] + "..."
            message_parts.append(f"{description_title}{truncated_desc}")
        else:
            message_parts.append(f"{description_title}{safe_description}")

    return "\n".join(message_parts)


async def get_new_ads(session: AsyncSession, query_params: dict):
    try:
        params = query_params.copy()
        params["size"] = params.pop("limit", 10)
        if params.get("only_title_search"):
            params["ot"] = 1

        params.pop("only_title_search", None)
        params.pop("city", None)

        params.setdefault("lang", "ru")
        params.setdefault("sort", "lst.d")

        logging.debug(f"Отправка запроса на {KUFAR_API_URL} с параметрами: {params}")
        response = await session.get(
            KUFAR_API_URL, params=params, impersonate="chrome110"
        )
        response.raise_for_status()
        return response.json().get("ads", [])
    except Exception as e:
        logging.error(f"Ошибка при запросе к Kufar API: {e}")
        return []

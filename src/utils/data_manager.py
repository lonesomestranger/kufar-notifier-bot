import json
import os

from src.config import CACHED_ADS_FILE, QUERIES_FILE, USERS_FILE


def ensure_data_dir():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)


def load_json(filename, default_value):
    ensure_data_dir()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value


def save_json(filename, data):
    ensure_data_dir()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_users():
    return load_json(USERS_FILE, [])


def save_users(users):
    save_json(USERS_FILE, users)


def load_queries():
    return load_json(QUERIES_FILE, {})


def save_queries(queries):
    save_json(QUERIES_FILE, queries)


def load_cached_ads():
    return set(load_json(CACHED_ADS_FILE, []))


def save_cached_ads(ad_ids):
    save_json(CACHED_ADS_FILE, list(ad_ids))

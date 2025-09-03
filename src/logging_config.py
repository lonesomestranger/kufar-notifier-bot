import logging
import os
from logging.handlers import TimedRotatingFileHandler

from src import config


def setup_logging():
    os.makedirs("logs", exist_ok=True)

    log_level_str = config.LOG_LEVEL.upper()
    log_level = logging.getLevelName(log_level_str)

    root_logger = logging.getLogger()

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(log_level)

    info_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    debug_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(info_formatter)

    info_file_handler = TimedRotatingFileHandler(
        "logs/bot.log", when="D", interval=1, backupCount=7, encoding="utf-8"
    )
    info_file_handler.setLevel(logging.WARNING)
    info_file_handler.setFormatter(info_formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(info_file_handler)

    if log_level == logging.DEBUG:
        debug_file_handler = TimedRotatingFileHandler(
            "logs/debug.log", when="D", interval=1, backupCount=7, encoding="utf-8"
        )
        debug_file_handler.setLevel(logging.DEBUG)
        debug_file_handler.setFormatter(debug_formatter)
        root_logger.addHandler(debug_file_handler)
        logging.info(
            "Отладочное логирование включено. Все сообщения будут писаться в debug.log"
        )

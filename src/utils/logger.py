"""ログ管理モジュール"""

import logging
import sys

from config.settings import LOG_FORMAT, LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """名前付きロガーを取得する"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    return logger

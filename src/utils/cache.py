"""キャッシュ管理モジュール"""

import time
from functools import wraps


class TTLCache:
    """TTL付きシンプルキャッシュ"""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str, ttl: int = 60):
        """キャッシュから値を取得（TTL秒以内なら有効）"""
        if key in self._store:
            value, timestamp = self._store[key]
            if time.time() - timestamp < ttl:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value):
        """キャッシュに値を格納"""
        self._store[key] = (value, time.time())

    def clear(self):
        """キャッシュをクリア"""
        self._store.clear()


# グローバルキャッシュインスタンス
cache = TTLCache()


def cached(ttl: int = 60):
    """TTL付きキャッシュデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            result = cache.get(key, ttl)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result)
            return result
        return wrapper
    return decorator

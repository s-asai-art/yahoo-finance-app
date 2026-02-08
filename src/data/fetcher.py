"""Yahoo!ファイナンスからデータを取得するモジュール"""

import time

import pandas as pd
import yfinance as yf

from src.utils.cache import cached
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _to_ticker(code: str) -> str:
    """銘柄コードをyfinance形式に変換"""
    code = code.strip().replace(".T", "")
    return f"{code}.T"


@cached(ttl=30)
def fetch_realtime_price(code: str) -> dict | None:
    """リアルタイム株価を取得する

    Returns:
        dict with keys: price, change, change_percent, open, high, low,
        volume, previous_close, market_cap, name, currency
    """
    try:
        ticker = yf.Ticker(_to_ticker(code))
        info = ticker.info
        if not info or "regularMarketPrice" not in info:
            # fast_infoからフォールバック
            fi = ticker.fast_info
            return {
                "price": getattr(fi, "last_price", None),
                "previous_close": getattr(fi, "previous_close", None),
                "open": getattr(fi, "open", None),
                "high": getattr(fi, "day_high", None),
                "low": getattr(fi, "day_low", None),
                "volume": getattr(fi, "last_volume", None),
                "market_cap": getattr(fi, "market_cap", None),
                "change": None,
                "change_percent": None,
                "name": code,
                "currency": getattr(fi, "currency", "JPY"),
            }

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        change = None
        change_pct = None
        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100

        return {
            "price": price,
            "change": change,
            "change_percent": change_pct,
            "open": info.get("regularMarketOpen") or info.get("open"),
            "high": info.get("regularMarketDayHigh") or info.get("dayHigh"),
            "low": info.get("regularMarketDayLow") or info.get("dayLow"),
            "volume": info.get("regularMarketVolume") or info.get("volume"),
            "previous_close": prev_close,
            "market_cap": info.get("marketCap"),
            "name": info.get("longName") or info.get("shortName", code),
            "currency": info.get("currency", "JPY"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "trading_value": None,  # 売買代金は別途計算
        }
    except Exception as e:
        logger.error(f"リアルタイム株価取得エラー ({code}): {e}")
        return None


@cached(ttl=300)
def fetch_historical_data(code: str, period: str = "1y") -> pd.DataFrame | None:
    """履歴データを取得する

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    try:
        ticker = yf.Ticker(_to_ticker(code))
        df = ticker.history(period=period)
        if df is None or df.empty:
            logger.warning(f"履歴データが空です ({code})")
            return None
        # カラム名を統一
        df.index.name = "Date"
        return df
    except Exception as e:
        logger.error(f"履歴データ取得エラー ({code}): {e}")
        return None


@cached(ttl=600)
def fetch_fundamental_data(code: str) -> dict | None:
    """ファンダメンタルデータを取得する"""
    try:
        ticker = yf.Ticker(_to_ticker(code))
        info = ticker.info
        if not info:
            return None

        return {
            "per": info.get("trailingPE") or info.get("forwardPE"),
            "pbr": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "equity_ratio": None,  # yfinanceでは直接取得不可
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "beta": info.get("beta"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
        }
    except Exception as e:
        logger.error(f"ファンダメンタルデータ取得エラー ({code}): {e}")
        return None


def fetch_board_posts(code: str, pages: int = 1) -> list[dict]:
    """掲示板データを取得する（既存scraperを利用）"""
    try:
        from scraper import BoardScraper
        scraper = BoardScraper()
        all_posts = []
        for page in range(1, pages + 1):
            posts = scraper.fetch(code, page=page)
            for p in posts:
                all_posts.append(p.to_dict())
            if page < pages:
                time.sleep(1.5)  # スクレイピング間隔
        return all_posts
    except Exception as e:
        logger.error(f"掲示板データ取得エラー ({code}): {e}")
        return []


@cached(ttl=300)
def fetch_nikkei225_data(period: str = "1y") -> pd.DataFrame | None:
    """日経225データを取得（ベータ値計算用）"""
    try:
        ticker = yf.Ticker("^N225")
        df = ticker.history(period=period)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.error(f"日経225データ取得エラー: {e}")
        return None

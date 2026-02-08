"""Yahoo!ファイナンスからデータを取得するモジュール"""

import re
import time

import numpy as np
import pandas as pd

from src.utils.cache import cached
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _to_ticker(code: str) -> str:
    """銘柄コードをyfinance形式に変換"""
    code = code.strip().replace(".T", "")
    return f"{code}.T"


def _parse_price_str(s: str) -> float | None:
    """価格文字列を数値に変換 ('1,234.5' -> 1234.5)"""
    if not s:
        return None
    try:
        return float(s.replace(",", "").replace("円", "").strip())
    except (ValueError, TypeError):
        return None


def _fetch_with_yfinance(code: str, method: str = "info"):
    """yfinanceでデータ取得を試みる（複数の方法でリトライ）"""
    import yfinance as yf
    ticker_str = _to_ticker(code)
    ticker = yf.Ticker(ticker_str)

    if method == "info":
        return ticker.info
    elif method == "fast_info":
        return ticker.fast_info
    elif method == "history":
        return ticker.history
    return None


def _fetch_realtime_via_scraper(code: str) -> dict | None:
    """既存スクレイパーでリアルタイム株価を取得（フォールバック）"""
    try:
        from scraper import StockScraper
        scraper = StockScraper()
        stock = scraper.fetch(code)

        price = _parse_price_str(stock.price)
        prev_close = _parse_price_str(stock.previous_close)

        change = None
        change_pct = None
        change_str = stock.change.strip() if stock.change else ""
        if change_str:
            # "前日比 +100 (+1.5%)" のようなフォーマットを解析
            parts = re.split(r'[（(]', change_str)
            change = _parse_price_str(parts[0])
            if len(parts) > 1:
                pct_str = parts[1].rstrip("）)%").strip()
                try:
                    change_pct = float(pct_str.replace(",", ""))
                except (ValueError, TypeError):
                    pass

        if change is None and price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else None

        return {
            "price": price,
            "change": change,
            "change_percent": change_pct,
            "open": _parse_price_str(stock.open_price),
            "high": _parse_price_str(stock.high),
            "low": _parse_price_str(stock.low),
            "volume": _parse_price_str(stock.volume),
            "previous_close": prev_close,
            "market_cap": _parse_price_str(stock.market_cap),
            "name": stock.name or code,
            "currency": "JPY",
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "trading_value": None,
        }
    except Exception as e:
        logger.error(f"スクレイパーによる株価取得エラー ({code}): {e}")
        return None


@cached(ttl=30)
def fetch_realtime_price(code: str) -> dict | None:
    """リアルタイム株価を取得する（yfinance -> scraper のフォールバック）"""

    # 方法1: yfinance info
    try:
        import yfinance as yf
        ticker = yf.Ticker(_to_ticker(code))
        info = ticker.info
        if info and ("regularMarketPrice" in info or "currentPrice" in info):
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
                "trading_value": None,
            }
    except Exception as e:
        logger.warning(f"yfinance info取得失敗 ({code}): {e}")

    # 方法2: yfinance fast_info
    try:
        import yfinance as yf
        ticker = yf.Ticker(_to_ticker(code))
        fi = ticker.fast_info
        price = getattr(fi, "last_price", None)
        if price is not None:
            prev_close = getattr(fi, "previous_close", None)
            change = (price - prev_close) if price and prev_close else None
            change_pct = (change / prev_close * 100) if change and prev_close else None
            return {
                "price": price,
                "previous_close": prev_close,
                "open": getattr(fi, "open", None),
                "high": getattr(fi, "day_high", None),
                "low": getattr(fi, "day_low", None),
                "volume": getattr(fi, "last_volume", None),
                "market_cap": getattr(fi, "market_cap", None),
                "change": change,
                "change_percent": change_pct,
                "name": code,
                "currency": getattr(fi, "currency", "JPY"),
                "fifty_two_week_high": None,
                "fifty_two_week_low": None,
                "trading_value": None,
            }
    except Exception as e:
        logger.warning(f"yfinance fast_info取得失敗 ({code}): {e}")

    # 方法3: yfinance history から最新値を取得
    try:
        import yfinance as yf
        ticker = yf.Ticker(_to_ticker(code))
        hist = ticker.history(period="5d")
        if hist is not None and not hist.empty:
            last = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else None
            price = float(last["Close"])
            prev_close = float(prev["Close"]) if prev is not None else None
            change = (price - prev_close) if prev_close else None
            change_pct = (change / prev_close * 100) if change and prev_close else None
            return {
                "price": price,
                "change": change,
                "change_percent": change_pct,
                "open": float(last["Open"]),
                "high": float(last["High"]),
                "low": float(last["Low"]),
                "volume": float(last["Volume"]),
                "previous_close": prev_close,
                "market_cap": None,
                "name": code,
                "currency": "JPY",
                "fifty_two_week_high": None,
                "fifty_two_week_low": None,
                "trading_value": None,
            }
    except Exception as e:
        logger.warning(f"yfinance history取得失敗 ({code}): {e}")

    # 方法4: 既存スクレイパーにフォールバック
    logger.info(f"スクレイパーにフォールバック ({code})")
    return _fetch_realtime_via_scraper(code)


@cached(ttl=300)
def fetch_historical_data(code: str, period: str = "1y") -> pd.DataFrame | None:
    """履歴データを取得する（yfinance -> download -> スクレイパーフォールバック）"""

    # 方法1: yfinance Ticker.history
    try:
        import yfinance as yf
        ticker = yf.Ticker(_to_ticker(code))
        df = ticker.history(period=period)
        if df is not None and not df.empty:
            df.index.name = "Date"
            return df
    except Exception as e:
        logger.warning(f"yfinance history取得失敗 ({code}): {e}")

    # 方法2: yfinance download
    try:
        import yfinance as yf
        df = yf.download(_to_ticker(code), period=period, progress=False)
        if df is not None and not df.empty:
            # マルチカラムインデックスを修正
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index.name = "Date"
            return df
    except Exception as e:
        logger.warning(f"yfinance download取得失敗 ({code}): {e}")

    # 方法3: スクレイパーからリアルタイム値のみのDataFrameを生成
    logger.info(f"スクレイパーフォールバックで単一行データを生成 ({code})")
    rt = _fetch_realtime_via_scraper(code)
    if rt and rt.get("price"):
        today = pd.Timestamp.now().normalize()
        df = pd.DataFrame({
            "Open": [rt.get("open") or rt["price"]],
            "High": [rt.get("high") or rt["price"]],
            "Low": [rt.get("low") or rt["price"]],
            "Close": [rt["price"]],
            "Volume": [rt.get("volume") or 0],
        }, index=pd.DatetimeIndex([today], name="Date"))
        return df

    return None


@cached(ttl=600)
def fetch_fundamental_data(code: str) -> dict | None:
    """ファンダメンタルデータを取得する"""
    try:
        import yfinance as yf
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
            "equity_ratio": None,
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
                time.sleep(1.5)
        return all_posts
    except Exception as e:
        logger.error(f"掲示板データ取得エラー ({code}): {e}")
        return []


@cached(ttl=300)
def fetch_nikkei225_data(period: str = "1y") -> pd.DataFrame | None:
    """日経225データを取得（ベータ値計算用）"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^N225")
        df = ticker.history(period=period)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.warning(f"日経225 history取得失敗: {e}")

    try:
        import yfinance as yf
        df = yf.download("^N225", period=period, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception as e:
        logger.error(f"日経225 download取得失敗: {e}")

    return None

"""Yahoo!ファイナンスからデータを取得するモジュール"""

import os
import re
import time

import numpy as np
import pandas as pd

from src.utils.cache import cached
from src.utils.logger import get_logger

logger = get_logger(__name__)

# --- SSL証明書の設定（Windows curl_cffi対策） ---
try:
    import certifi
    ca_bundle = certifi.where()
    os.environ.setdefault("CURL_CA_BUNDLE", ca_bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
except ImportError:
    pass


def _to_ticker(code: str) -> str:
    """銘柄コードをyfinance形式に変換"""
    code = code.strip().replace(".T", "")
    return f"{code}.T"


def _parse_price_str(s: str) -> float | None:
    """価格文字列を数値に変換 ('1,234.5' -> 1234.5)"""
    if not s:
        return None
    try:
        cleaned = re.sub(r'[^\d.\-+]', '', s.replace(",", ""))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _fetch_realtime_via_scraper(code: str) -> dict | None:
    """既存スクレイパーでリアルタイム株価を取得（フォールバック）"""
    try:
        from scraper import StockScraper
        scraper = StockScraper()
        stock = scraper.fetch(code)

        price = _parse_price_str(stock.price)
        if not price:
            return None

        prev_close = _parse_price_str(stock.previous_close)

        change = None
        change_pct = None
        change_str = stock.change.strip() if stock.change else ""
        if change_str:
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
        logger.warning(f"スクレイパーによる株価取得エラー ({code}): {e}")
        return None


# 失敗キャッシュ: 同じコードで連続失敗を防ぐ
_failure_cache: dict[str, float] = {}
_FAILURE_TTL = 120  # 失敗後120秒はリトライしない


def _is_recently_failed(key: str) -> bool:
    if key in _failure_cache:
        if time.time() - _failure_cache[key] < _FAILURE_TTL:
            return True
        del _failure_cache[key]
    return False


def _mark_failed(key: str):
    _failure_cache[key] = time.time()


@cached(ttl=60)
def fetch_realtime_price(code: str) -> dict | None:
    """リアルタイム株価を取得する（yfinance -> scraper のフォールバック）"""

    # yfinanceの失敗キャッシュチェック
    yf_failed = _is_recently_failed(f"yf_realtime_{code}")

    if not yf_failed:
        # 方法1: yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(_to_ticker(code))

            # fast_info が最も軽量
            try:
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
            except Exception:
                pass

            # info（重いが詳細）
            try:
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
            except Exception:
                pass

            # history から最新値
            try:
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
            except Exception:
                pass

            # 全方法失敗
            _mark_failed(f"yf_realtime_{code}")
        except Exception as e:
            logger.warning(f"yfinance全体エラー ({code}): {e}")
            _mark_failed(f"yf_realtime_{code}")

    # フォールバック: 既存スクレイパー
    return _fetch_realtime_via_scraper(code)


@cached(ttl=300)
def fetch_historical_data(code: str, period: str = "1y") -> pd.DataFrame | None:
    """履歴データを取得する"""

    if _is_recently_failed(f"yf_hist_{code}_{period}"):
        return _fallback_historical(code)

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
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index.name = "Date"
            return df
    except Exception as e:
        logger.warning(f"yfinance download取得失敗 ({code}): {e}")

    _mark_failed(f"yf_hist_{code}_{period}")
    return _fallback_historical(code)


def _fallback_historical(code: str) -> pd.DataFrame | None:
    """スクレイパーからの最小限の履歴データ"""
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
    if _is_recently_failed(f"yf_fund_{code}"):
        return None

    try:
        import yfinance as yf
        ticker = yf.Ticker(_to_ticker(code))
        info = ticker.info
        if not info:
            _mark_failed(f"yf_fund_{code}")
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
        logger.warning(f"ファンダメンタルデータ取得エラー ({code}): {e}")
        _mark_failed(f"yf_fund_{code}")
        return None


def fetch_board_posts(code: str, pages: int = 1) -> list[dict]:
    """掲示板データを取得する（既存scraperを利用）"""
    if _is_recently_failed(f"board_{code}"):
        return []

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
        logger.warning(f"掲示板データ取得エラー ({code}): {e}")
        _mark_failed(f"board_{code}")
        return []


@cached(ttl=300)
def fetch_nikkei225_data(period: str = "1y") -> pd.DataFrame | None:
    """日経225データを取得（ベータ値計算用）"""
    if _is_recently_failed("yf_nikkei"):
        return None

    try:
        import yfinance as yf
        ticker = yf.Ticker("^N225")
        df = ticker.history(period=period)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    try:
        import yfinance as yf
        df = yf.download("^N225", period=period, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception:
        pass

    _mark_failed("yf_nikkei")
    return None

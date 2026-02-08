"""Yahoo!ファイナンスから株価情報を取得するモジュール"""

import os
import re
import ssl
from dataclasses import dataclass, field

import requests
import urllib3
from bs4 import BeautifulSoup

# SSL証明書検証をグローバルに無効化（yfinance内部のHTTPクライアント含む）
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import yfinance as yf

    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

BASE_URL = "https://finance.yahoo.co.jp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass
class StockPrice:
    """株価情報を格納するデータクラス"""

    code: str = ""
    name: str = ""
    market: str = ""
    price: str = ""
    change: str = ""
    change_percent: str = ""
    previous_close: str = ""
    open_price: str = ""
    high: str = ""
    low: str = ""
    volume: str = ""
    market_cap: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "銘柄コード": self.code,
            "銘柄名": self.name,
            "市場": self.market,
            "現在値": self.price,
            "前日比": self.change,
            "前日比(%)": self.change_percent,
            "前日終値": self.previous_close,
            "始値": self.open_price,
            "高値": self.high,
            "安値": self.low,
            "出来高": self.volume,
            "時価総額": self.market_cap,
            **self.extra,
        }


class StockScraper:
    """Yahoo!ファイナンスから株価情報をスクレイピングするクラス"""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False

    def fetch(self, code: str) -> StockPrice:
        """株価情報を取得する

        Args:
            code: 銘柄コード (例: "7203", "7203.T")

        Returns:
            StockPrice: 株価情報
        """
        # yfinanceが利用可能ならAPIベースで取得し、失敗時はスクレイピングへ
        if HAS_YFINANCE:
            try:
                return self._fetch_via_yfinance(code)
            except Exception:
                pass
        return self._fetch_via_scraping(code)

    def _normalize_code(self, code: str) -> str:
        """銘柄コードを正規化する（.Tサフィックスを確保）"""
        code = code.strip()
        if re.match(r"^\d{4}$", code):
            return f"{code}.T"
        return code

    def _fetch_via_yfinance(self, code: str) -> StockPrice:
        """yfinanceライブラリ経由で株価を取得"""
        ticker_code = self._normalize_code(code)
        ticker = yf.Ticker(ticker_code)
        info = ticker.info

        return StockPrice(
            code=code,
            name=info.get("longName") or info.get("shortName", ""),
            market=info.get("exchange", ""),
            price=str(info.get("currentPrice") or info.get("regularMarketPrice", "")),
            change=str(info.get("regularMarketChange", "")),
            change_percent=str(info.get("regularMarketChangePercent", "")),
            previous_close=str(info.get("previousClose", "")),
            open_price=str(info.get("open") or info.get("regularMarketOpen", "")),
            high=str(info.get("dayHigh") or info.get("regularMarketDayHigh", "")),
            low=str(info.get("dayLow") or info.get("regularMarketDayLow", "")),
            volume=str(info.get("volume") or info.get("regularMarketVolume", "")),
            market_cap=str(info.get("marketCap", "")),
            extra={
                "52週高値": str(info.get("fiftyTwoWeekHigh", "")),
                "52週安値": str(info.get("fiftyTwoWeekLow", "")),
                "PER": str(info.get("trailingPE", "")),
                "PBR": str(info.get("priceToBook", "")),
                "配当利回り": str(info.get("dividendYield", "")),
            },
        )

    def _fetch_via_scraping(self, code: str) -> StockPrice:
        """Webスクレイピングで株価を取得"""
        clean_code = code.replace(".T", "").strip()
        url = f"{BASE_URL}/quote/{clean_code}.T"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        stock = StockPrice(code=clean_code)

        # 銘柄名
        name_el = soup.select_one("h1.Symbol, [class*='StockName'] h1, .hp_stockDetail h1")
        if name_el:
            stock.name = name_el.get_text(strip=True)

        # 現在値
        price_el = soup.select_one(
            "[class*='StocksPrice'] span, "
            "[class*='currentPrice'], "
            ".stoksPrice, "
            'span[data-field="regularMarketPrice"]'
        )
        if price_el:
            stock.price = price_el.get_text(strip=True)

        # 前日比・変動率
        change_el = soup.select_one(
            "[class*='PriceChange'], [class*='change'], .stoksChange"
        )
        if change_el:
            text = change_el.get_text(strip=True)
            parts = re.split(r"[（(]", text)
            stock.change = parts[0].strip()
            if len(parts) > 1:
                stock.change_percent = parts[1].rstrip("）)").strip()

        # 詳細テーブルからデータを抽出
        detail_mapping = {
            "前日終値": "previous_close",
            "始値": "open_price",
            "高値": "high",
            "安値": "low",
            "出来高": "volume",
            "時価総額": "market_cap",
        }
        for row in soup.select("dl dt, li span, table th"):
            label = row.get_text(strip=True)
            for jp_label, attr in detail_mapping.items():
                if jp_label in label:
                    value_el = row.find_next_sibling("dd") or row.find_next("td") or row.find_next("span")
                    if value_el:
                        setattr(stock, attr, value_el.get_text(strip=True))

        return stock

    def fetch_multiple(self, codes: list[str]) -> list[StockPrice]:
        """複数銘柄の株価を一括取得"""
        return [self.fetch(code) for code in codes]

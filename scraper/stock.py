"""Yahoo!ファイナンスから株価情報を取得するモジュール"""

import re
import ssl
import urllib.request
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# SSL証明書検証を無効化したコンテキスト
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

BASE_URL = "https://finance.yahoo.co.jp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def _fetch_html(url: str) -> str:
    """URLからHTMLを取得する（標準ライブラリのみ使用）"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return resp.read().decode("utf-8", errors="replace")


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

    def fetch(self, code: str) -> StockPrice:
        """株価情報を取得する

        Args:
            code: 銘柄コード (例: "7203", "7203.T")

        Returns:
            StockPrice: 株価情報
        """
        clean_code = code.replace(".T", "").strip()
        url = f"{BASE_URL}/quote/{clean_code}.T"
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

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

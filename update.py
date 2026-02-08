#!/usr/bin/env python3
"""ファイルを最新版に更新するスクリプト"""
import os

os.makedirs("scraper", exist_ok=True)

# --- scraper/__init__.py ---
with open("scraper/__init__.py", "w", encoding="utf-8") as f:
    f.write("""from .stock import StockScraper
from .board import BoardScraper

__all__ = ["StockScraper", "BoardScraper"]
""")
print("Updated: scraper/__init__.py")

# --- scraper/stock.py ---
with open("scraper/stock.py", "w", encoding="utf-8") as f:
    f.write('''"""Yahoo!ファイナンスから株価情報を取得するモジュール"""

import re
import ssl
import urllib.request
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

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
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return resp.read().decode("utf-8", errors="replace")


@dataclass
class StockPrice:
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

    def fetch(self, code: str) -> StockPrice:
        clean_code = code.replace(".T", "").strip()
        url = f"{BASE_URL}/quote/{clean_code}.T"
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        stock = StockPrice(code=clean_code)

        name_el = soup.select_one("h1.Symbol, [class*=\'StockName\'] h1, .hp_stockDetail h1")
        if name_el:
            stock.name = name_el.get_text(strip=True)

        price_el = soup.select_one(
            "[class*=\'StocksPrice\'] span, "
            "[class*=\'currentPrice\'], "
            ".stoksPrice, "
            \'span[data-field="regularMarketPrice"]\'
        )
        if price_el:
            stock.price = price_el.get_text(strip=True)

        change_el = soup.select_one(
            "[class*=\'PriceChange\'], [class*=\'change\'], .stoksChange"
        )
        if change_el:
            text = change_el.get_text(strip=True)
            parts = re.split(r"[（(]", text)
            stock.change = parts[0].strip()
            if len(parts) > 1:
                stock.change_percent = parts[1].rstrip("）)").strip()

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
        return [self.fetch(code) for code in codes]
''')
print("Updated: scraper/stock.py")

# --- scraper/board.py ---
with open("scraper/board.py", "w", encoding="utf-8") as f:
    f.write('''"""Yahoo!ファイナンス掲示板から投稿情報を取得するモジュール"""

import re
import ssl
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

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
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return resp.read().decode("utf-8", errors="replace")


@dataclass
class BoardPost:
    number: str = ""
    title: str = ""
    body: str = ""
    author: str = ""
    timestamp: str = ""
    agrees: str = ""
    disagrees: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "番号": self.number,
            "タイトル": self.title,
            "本文": self.body,
            "投稿者": self.author,
            "日時": self.timestamp,
            "そう思う": self.agrees,
            "そう思わない": self.disagrees,
            "URL": self.url,
        }


class BoardScraper:

    def _build_board_url(self, code: str) -> str:
        clean_code = code.replace(".T", "").strip()
        return f"{BASE_URL}/cm/message/1{clean_code}"

    def _find_board_url(self, code: str) -> str:
        clean_code = code.replace(".T", "").strip()
        direct_url = self._build_board_url(code)
        try:
            html = _fetch_html(direct_url)
            if html:
                return direct_url
        except Exception:
            pass

        search_url = f"{BASE_URL}/search/?query={clean_code}"
        try:
            html = _fetch_html(search_url)
            soup = BeautifulSoup(html, "lxml")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/cm/message/" in href and clean_code in href:
                    return urljoin(BASE_URL, href)
        except Exception:
            pass

        return direct_url

    def fetch(self, code: str, page: int = 1) -> list[BoardPost]:
        board_url = self._find_board_url(code)
        if page > 1:
            board_url = f"{board_url}?p={page}"

        html = _fetch_html(board_url)
        return self._parse_board_page(html, board_url)

    def _parse_board_page(self, html: str, base_url: str) -> list[BoardPost]:
        soup = BeautifulSoup(html, "lxml")
        posts = []

        article_selectors = [
            "li.MessageList",
            "article.Message",
            "[class*=\'messageItem\']",
            "[class*=\'comment\']",
            ".textWrap",
        ]

        articles = []
        for selector in article_selectors:
            articles = soup.select(selector)
            if articles:
                break

        if not articles:
            articles = soup.select("table.boardTbl tr, table tr.MessageItem")

        for article in articles:
            post = self._parse_post(article, base_url)
            if post and (post.title or post.body):
                posts.append(post)

        return posts

    def _parse_post(self, element, base_url: str):
        post = BoardPost()

        num_el = element.select_one("[class*=\'number\'], .num, .msgIdx, span.idx")
        if num_el:
            post.number = num_el.get_text(strip=True)

        title_el = element.select_one("[class*=\'title\'], .subject, h3, h4, a.msgTitle")
        if title_el:
            post.title = title_el.get_text(strip=True)
            link = title_el.find("a", href=True) if title_el.name != "a" else title_el
            if link and link.get("href"):
                post.url = urljoin(base_url, link["href"])

        body_el = element.select_one("[class*=\'body\'], [class*=\'content\'], .msgBody, .txtBody, p")
        if body_el:
            post.body = body_el.get_text(strip=True)

        author_el = element.select_one("[class*=\'author\'], [class*=\'user\'], .userName, .poster")
        if author_el:
            post.author = author_el.get_text(strip=True)

        time_el = element.select_one("time, [class*=\'date\'], [class*=\'time\'], .msgDate")
        if time_el:
            post.timestamp = time_el.get("datetime", "") or time_el.get_text(strip=True)

        vote_els = element.select("[class*=\'agree\'], [class*=\'vote\'], .agreeCount")
        if len(vote_els) >= 2:
            post.agrees = vote_els[0].get_text(strip=True)
            post.disagrees = vote_els[1].get_text(strip=True)
        elif len(vote_els) == 1:
            post.agrees = vote_els[0].get_text(strip=True)

        return post

    def fetch_post_detail(self, url: str) -> BoardPost:
        html = _fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        post = BoardPost(url=url)

        title_el = soup.select_one("h1, h2.subject, [class*=\'messageTitle\']")
        if title_el:
            post.title = title_el.get_text(strip=True)

        body_el = soup.select_one("[class*=\'messageBody\'], [class*=\'content\'], .msgBody")
        if body_el:
            post.body = body_el.get_text(strip=True)

        author_el = soup.select_one("[class*=\'author\'], .userName, .poster")
        if author_el:
            post.author = author_el.get_text(strip=True)

        time_el = soup.select_one("time, [class*=\'date\'], .msgDate")
        if time_el:
            post.timestamp = time_el.get("datetime", "") or time_el.get_text(strip=True)

        return post
''')
print("Updated: scraper/board.py")

# --- requirements.txt ---
with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write("beautifulsoup4>=4.12.0\nlxml>=5.0.0\n")
print("Updated: requirements.txt")

print("\n全ファイルを更新しました！")
print("次のコマンドを実行してください: python main.py stock 7203")

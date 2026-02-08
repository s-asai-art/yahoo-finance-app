"""Yahoo!ファイナンス掲示板から投稿情報を取得するモジュール"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://finance.yahoo.co.jp"
BOARD_URL = f"{BASE_URL}/cm/message"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass
class BoardPost:
    """掲示板の投稿を格納するデータクラス"""

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
    """Yahoo!ファイナンス掲示板をスクレイピングするクラス"""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def _build_board_url(self, code: str) -> str:
        """掲示板のURLを構築する

        Yahoo!ファイナンス掲示板のURLは以下の形式:
        https://finance.yahoo.co.jp/cm/message/1{code}/{encoded_name}
        銘柄コードからトップレベルの掲示板一覧ページへアクセスし、
        実際の掲示板URLを取得する。
        """
        clean_code = code.replace(".T", "").strip()
        return f"{BASE_URL}/cm/message/1{clean_code}"

    def _find_board_url(self, code: str) -> str:
        """銘柄コードから掲示板URLを探す"""
        clean_code = code.replace(".T", "").strip()

        # まず直接的なURLパターンを試す
        direct_url = self._build_board_url(code)
        try:
            resp = self.session.get(direct_url, timeout=15, allow_redirects=True)
            if resp.status_code == 200:
                return resp.url
        except requests.RequestException:
            pass

        # 検索ページから掲示板リンクを取得
        search_url = f"{BASE_URL}/search/?query={clean_code}"
        try:
            resp = self.session.get(search_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/cm/message/" in href and clean_code in href:
                    return urljoin(BASE_URL, href)
        except requests.RequestException:
            pass

        return direct_url

    def fetch(self, code: str, page: int = 1) -> list[BoardPost]:
        """掲示板の投稿一覧を取得する

        Args:
            code: 銘柄コード (例: "7203")
            page: ページ番号 (デフォルト: 1)

        Returns:
            list[BoardPost]: 投稿リスト
        """
        board_url = self._find_board_url(code)
        if page > 1:
            board_url = f"{board_url}?p={page}"

        resp = self.session.get(board_url, timeout=15)
        resp.raise_for_status()
        return self._parse_board_page(resp.text, board_url)

    def _parse_board_page(self, html: str, base_url: str) -> list[BoardPost]:
        """掲示板ページのHTMLをパースして投稿リストを返す"""
        soup = BeautifulSoup(html, "lxml")
        posts = []

        # 投稿要素を探す（複数のセレクタパターンに対応）
        article_selectors = [
            "li.MessageList",
            "article.Message",
            "[class*='messageItem']",
            "[class*='comment']",
            ".textWrap",
        ]

        articles = []
        for selector in article_selectors:
            articles = soup.select(selector)
            if articles:
                break

        if not articles:
            # フォールバック: テーブル形式の掲示板
            articles = soup.select("table.boardTbl tr, table tr.MessageItem")

        for article in articles:
            post = self._parse_post(article, base_url)
            if post and (post.title or post.body):
                posts.append(post)

        return posts

    def _parse_post(self, element: BeautifulSoup, base_url: str) -> BoardPost | None:
        """個別の投稿要素をパースする"""
        post = BoardPost()

        # 番号
        num_el = element.select_one(
            "[class*='number'], .num, .msgIdx, span.idx"
        )
        if num_el:
            post.number = num_el.get_text(strip=True)

        # タイトル
        title_el = element.select_one(
            "[class*='title'], .subject, h3, h4, a.msgTitle"
        )
        if title_el:
            post.title = title_el.get_text(strip=True)
            link = title_el.find("a", href=True) if title_el.name != "a" else title_el
            if link and link.get("href"):
                post.url = urljoin(base_url, link["href"])

        # 本文
        body_el = element.select_one(
            "[class*='body'], [class*='content'], .msgBody, .txtBody, p"
        )
        if body_el:
            post.body = body_el.get_text(strip=True)

        # 投稿者
        author_el = element.select_one(
            "[class*='author'], [class*='user'], .userName, .poster"
        )
        if author_el:
            post.author = author_el.get_text(strip=True)

        # 日時
        time_el = element.select_one(
            "time, [class*='date'], [class*='time'], .msgDate"
        )
        if time_el:
            post.timestamp = (
                time_el.get("datetime", "") or time_el.get_text(strip=True)
            )

        # そう思う / そう思わない
        vote_els = element.select("[class*='agree'], [class*='vote'], .agreeCount")
        if len(vote_els) >= 2:
            post.agrees = vote_els[0].get_text(strip=True)
            post.disagrees = vote_els[1].get_text(strip=True)
        elif len(vote_els) == 1:
            post.agrees = vote_els[0].get_text(strip=True)

        return post

    def fetch_post_detail(self, url: str) -> BoardPost:
        """個別投稿の詳細ページを取得する"""
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        post = BoardPost(url=url)

        title_el = soup.select_one(
            "h1, h2.subject, [class*='messageTitle']"
        )
        if title_el:
            post.title = title_el.get_text(strip=True)

        body_el = soup.select_one(
            "[class*='messageBody'], [class*='content'], .msgBody"
        )
        if body_el:
            post.body = body_el.get_text(strip=True)

        author_el = soup.select_one(
            "[class*='author'], .userName, .poster"
        )
        if author_el:
            post.author = author_el.get_text(strip=True)

        time_el = soup.select_one("time, [class*='date'], .msgDate")
        if time_el:
            post.timestamp = (
                time_el.get("datetime", "") or time_el.get_text(strip=True)
            )

        return post

#!/usr/bin/env python3
"""Yahoo!ファイナンス 株価・掲示板情報取得ツール

使い方:
    # 株価情報を取得
    python main.py stock 7203
    python main.py stock 7203 6758 9984

    # 掲示板情報を取得
    python main.py board 7203
    python main.py board 7203 --page 2

    # JSON形式で出力
    python main.py stock 7203 --json

    # CSV形式で出力
    python main.py stock 7203 6758 9984 --csv
"""

import argparse
import csv
import io
import json
import sys

from scraper import BoardScraper, StockScraper


def format_stock_table(stocks: list) -> str:
    """株価情報をテーブル形式でフォーマットする"""
    lines = []
    for stock in stocks:
        data = stock.to_dict()
        lines.append("=" * 50)
        for key, value in data.items():
            if value:
                lines.append(f"  {key:<14} : {value}")
    lines.append("=" * 50)
    return "\n".join(lines)


def format_board_table(posts: list) -> str:
    """掲示板投稿をテーブル形式でフォーマットする"""
    if not posts:
        return "投稿が見つかりませんでした。"

    lines = []
    for post in posts:
        lines.append("-" * 50)
        if post.number:
            lines.append(f"  No.{post.number}")
        if post.title:
            lines.append(f"  タイトル : {post.title}")
        if post.body:
            body = post.body[:200] + "..." if len(post.body) > 200 else post.body
            lines.append(f"  本文     : {body}")
        if post.author:
            lines.append(f"  投稿者   : {post.author}")
        if post.timestamp:
            lines.append(f"  日時     : {post.timestamp}")
        if post.agrees or post.disagrees:
            lines.append(f"  評価     : そう思う {post.agrees} / そう思わない {post.disagrees}")
    lines.append("-" * 50)
    return "\n".join(lines)


def cmd_stock(args: argparse.Namespace) -> None:
    """株価情報を取得して表示する"""
    scraper = StockScraper()
    stocks = scraper.fetch_multiple(args.codes)

    if args.json:
        data = [s.to_dict() for s in stocks]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.csv:
        if not stocks:
            return
        buf = io.StringIO()
        keys = list(stocks[0].to_dict().keys())
        writer = csv.DictWriter(buf, fieldnames=keys)
        writer.writeheader()
        for s in stocks:
            writer.writerow(s.to_dict())
        print(buf.getvalue())
    else:
        print(format_stock_table(stocks))


def cmd_board(args: argparse.Namespace) -> None:
    """掲示板情報を取得して表示する"""
    scraper = BoardScraper()
    posts = scraper.fetch(args.code, page=args.page)

    if args.json:
        data = [p.to_dict() for p in posts]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"\n【{args.code}】掲示板 (ページ {args.page})")
        print(format_board_table(posts))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Yahoo!ファイナンス 株価・掲示板情報取得ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stock サブコマンド
    stock_parser = subparsers.add_parser("stock", help="株価情報を取得")
    stock_parser.add_argument(
        "codes",
        nargs="+",
        help="銘柄コード (例: 7203 6758 9984)",
    )
    stock_parser.add_argument("--json", action="store_true", help="JSON形式で出力")
    stock_parser.add_argument("--csv", action="store_true", help="CSV形式で出力")
    stock_parser.set_defaults(func=cmd_stock)

    # board サブコマンド
    board_parser = subparsers.add_parser("board", help="掲示板情報を取得")
    board_parser.add_argument("code", help="銘柄コード (例: 7203)")
    board_parser.add_argument("--page", type=int, default=1, help="ページ番号")
    board_parser.add_argument("--json", action="store_true", help="JSON形式で出力")
    board_parser.set_defaults(func=cmd_board)

    args = parser.parse_args()

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n中断しました。")
        sys.exit(130)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""アプリケーション設定"""

# デフォルト銘柄コード
DEFAULT_STOCK_CODE = "7203"

# デフォルト更新間隔（秒）
DEFAULT_REFRESH_INTERVAL = 60

# 履歴データ期間
DEFAULT_HISTORY_PERIOD = "1y"

# チャート期間オプション
CHART_PERIODS = {
    "1ヶ月": "1mo",
    "3ヶ月": "3mo",
    "6ヶ月": "6mo",
    "1年": "1y",
    "2年": "2y",
    "5年": "5y",
}

# 更新間隔オプション（秒）
REFRESH_INTERVALS = {
    "30秒": 30,
    "1分": 60,
    "5分": 300,
}

# テクニカル指標のデフォルト設定
TECHNICAL_DEFAULTS = {
    "ma_short": 5,
    "ma_medium": 25,
    "ma_long": 75,
    "ma_very_long": 200,
    "bb_period": 20,
    "bb_std": 2,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
}

# センチメントスコアのしきい値
SENTIMENT_THRESHOLDS = {
    "very_positive": 0.5,
    "positive": 0.1,
    "negative": -0.1,
    "very_negative": -0.5,
}

# Streamlitポート
STREAMLIT_PORT = 8501

# データベースパス
DB_PATH = "data/stock.db"

# ログ設定
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# スクレイピング設定
SCRAPE_DELAY = 1.5  # リクエスト間隔（秒）
MAX_BOARD_PAGES = 5  # 掲示板最大取得ページ数

# お気に入り銘柄のデフォルト
DEFAULT_FAVORITES = [
    ("7203", "トヨタ自動車"),
    ("6758", "ソニーグループ"),
    ("9984", "ソフトバンクグループ"),
    ("6861", "キーエンス"),
    ("8306", "三菱UFJ"),
]

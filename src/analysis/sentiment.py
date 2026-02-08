"""センチメント分析モジュール"""

import re
from collections import Counter


# 日本語ポジティブ・ネガティブ辞書（基本版）
POSITIVE_WORDS = [
    "上がる", "上昇", "買い", "好調", "期待", "利益", "増収", "増益",
    "最高", "成長", "回復", "反発", "強い", "高値", "ストップ高",
    "好材料", "サプライズ", "良い", "いい", "素晴らしい", "楽観",
    "爆益", "含み益", "ホールド", "ガチホ", "上方修正", "黒字転換",
    "底打ち", "底値", "安値買い", "仕込み", "チャンス", "割安",
    "大幅高", "急騰", "暴騰", "高配当", "増配", "自社株買い",
    "好決算", "過去最高", "業績好調", "受注増", "売上増",
]

NEGATIVE_WORDS = [
    "下がる", "下落", "売り", "不調", "不安", "損失", "減収", "減益",
    "最低", "低迷", "暴落", "急落", "弱い", "安値", "ストップ安",
    "悪材料", "リスク", "悪い", "ダメ", "やばい", "悲観",
    "爆損", "含み損", "損切り", "ロスカット", "下方修正", "赤字転落",
    "天井", "高値掴み", "危険", "割高", "大幅安", "暴落",
    "悪決算", "業績悪化", "受注減", "売上減", "債務超過",
    "ナンピン", "塩漬け", "恐怖", "不祥事", "訴訟",
]


def analyze_sentiment(text: str) -> dict:
    """テキストのセンチメントを分析する

    Returns:
        dict with keys: score (-1.0 to 1.0), label, positive_count, negative_count
    """
    if not text:
        return {"score": 0.0, "label": "中立", "positive_count": 0, "negative_count": 0}

    text_lower = text.lower()

    pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)

    total = pos_count + neg_count
    if total == 0:
        score = 0.0
    else:
        score = (pos_count - neg_count) / total

    if score > 0.2:
        label = "ポジティブ"
    elif score < -0.2:
        label = "ネガティブ"
    else:
        label = "中立"

    return {
        "score": score,
        "label": label,
        "positive_count": pos_count,
        "negative_count": neg_count,
    }


def analyze_posts_sentiment(posts: list[dict]) -> dict:
    """掲示板投稿群のセンチメントを分析する

    Returns:
        dict with keys: average_score, label, total_posts, sentiment_distribution,
        scores_over_time, keywords
    """
    if not posts:
        return {
            "average_score": 0.0,
            "label": "データなし",
            "total_posts": 0,
            "sentiment_distribution": {"ポジティブ": 0, "中立": 0, "ネガティブ": 0},
            "post_sentiments": [],
            "keywords": [],
        }

    sentiments = []
    distribution = {"ポジティブ": 0, "中立": 0, "ネガティブ": 0}
    all_text = []

    for post in posts:
        text = f"{post.get('タイトル', '')} {post.get('本文', '')}"
        result = analyze_sentiment(text)
        result["timestamp"] = post.get("日時", "")
        sentiments.append(result)
        distribution[result["label"]] += 1
        all_text.append(text)

    scores = [s["score"] for s in sentiments]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    if avg_score > 0.2:
        overall_label = "ポジティブ"
    elif avg_score < -0.2:
        overall_label = "ネガティブ"
    else:
        overall_label = "中立"

    # キーワード抽出
    keywords = extract_keywords(" ".join(all_text))

    return {
        "average_score": avg_score,
        "label": overall_label,
        "total_posts": len(posts),
        "sentiment_distribution": distribution,
        "post_sentiments": sentiments,
        "keywords": keywords,
    }


def extract_keywords(text: str, top_n: int = 20) -> list[tuple[str, int]]:
    """テキストからキーワードを抽出する（簡易版）"""
    # 数字・記号・一般的な助詞等を除去
    stopwords = {
        "の", "に", "は", "を", "た", "が", "で", "て", "と", "し", "れ", "さ",
        "ある", "いる", "も", "する", "から", "な", "こと", "として", "い", "や",
        "れる", "など", "なっ", "ない", "この", "ため", "その", "あっ", "よう",
        "また", "もの", "という", "あり", "まで", "られ", "なる", "へ", "か",
        "だ", "これ", "によって", "により", "おり", "より", "による", "ず",
        "なり", "られる", "において", "ここ", "それ", "どう", "そう", "です",
        "ます", "けど", "って", "www", "笑", "思う", "思い", "思っ",
    }

    # 簡易的にカタカナ語、漢字語を抽出
    # カタカナ2文字以上
    katakana = re.findall(r'[\u30A0-\u30FF]{2,}', text)
    # 漢字2文字以上
    kanji = re.findall(r'[\u4E00-\u9FFF]{2,6}', text)
    # アルファベット2文字以上
    alpha = re.findall(r'[A-Za-z]{2,}', text)

    words = katakana + kanji + [w.upper() for w in alpha]
    words = [w for w in words if w not in stopwords and len(w) >= 2]

    counter = Counter(words)
    return counter.most_common(top_n)


def detect_sentiment_change(current_score: float, previous_score: float) -> dict | None:
    """センチメントの急変を検出する"""
    change = current_score - previous_score
    if abs(change) > 0.3:
        direction = "改善" if change > 0 else "悪化"
        return {
            "direction": direction,
            "change": change,
            "current": current_score,
            "previous": previous_score,
            "message": f"センチメント{direction}: {previous_score:.2f} → {current_score:.2f}",
        }
    return None

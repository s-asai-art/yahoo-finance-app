"""投資判断エンジン"""

from src.utils.logger import get_logger

logger = get_logger(__name__)

# シグナルの重み付け
WEIGHTS = {
    "technical": 0.30,
    "fundamental": 0.25,
    "sentiment": 0.15,
    "ml_trend": 0.15,
    "risk": 0.15,
}


def calculate_investment_score(
    technical_signals: list[dict],
    fundamental_evaluations: list[dict],
    sentiment_data: dict | None,
    trend_prediction: dict | None,
    risk_data: dict | None,
) -> dict:
    """総合投資判断スコアを算出する

    Returns:
        dict with keys: total_score, recommendation, confidence,
        component_scores, reasons, entry_exit
    """
    component_scores = {}
    reasons = []

    # 1. テクニカル分析スコア
    tech_score = _calculate_technical_score(technical_signals)
    component_scores["technical"] = tech_score
    if tech_score > 0.3:
        reasons.append("テクニカル指標が買いシグナル")
    elif tech_score < -0.3:
        reasons.append("テクニカル指標が売りシグナル")

    # 2. ファンダメンタル分析スコア
    fund_score = _calculate_fundamental_score(fundamental_evaluations)
    component_scores["fundamental"] = fund_score
    if fund_score > 0.3:
        reasons.append("ファンダメンタルが良好")
    elif fund_score < -0.3:
        reasons.append("ファンダメンタルに懸念")

    # 3. センチメントスコア
    sent_score = 0.0
    if sentiment_data and sentiment_data.get("average_score") is not None:
        sent_score = sentiment_data["average_score"]
        component_scores["sentiment"] = sent_score
        if sent_score > 0.2:
            reasons.append("掲示板のセンチメントがポジティブ")
        elif sent_score < -0.2:
            reasons.append("掲示板のセンチメントがネガティブ")
    else:
        component_scores["sentiment"] = 0.0

    # 4. ML予測スコア
    ml_score = 0.0
    if trend_prediction:
        trend = trend_prediction.get("trend", "横ばい")
        confidence = trend_prediction.get("confidence", 0.5)
        if trend == "上昇":
            ml_score = confidence * 0.8
            reasons.append(f"AI予測: 上昇トレンド (信頼度{confidence:.0%})")
        elif trend == "下降":
            ml_score = -confidence * 0.8
            reasons.append(f"AI予測: 下降トレンド (信頼度{confidence:.0%})")
        else:
            ml_score = 0.0
    component_scores["ml_trend"] = ml_score

    # 5. リスクスコア（リスクが高いほどマイナス）
    risk_score = 0.0
    if risk_data:
        risk_level = risk_data.get("risk_score", 50)
        risk_score = (50 - risk_level) / 50  # 50基準で正負変換
        component_scores["risk"] = risk_score
        if risk_level > 70:
            reasons.append("リスクが高い水準")
        elif risk_level < 30:
            reasons.append("リスクが低い水準")
    else:
        component_scores["risk"] = 0.0

    # 総合スコア算出
    total_score = sum(
        component_scores.get(key, 0) * weight
        for key, weight in WEIGHTS.items()
    )

    # 推奨判断
    if total_score > 0.3:
        recommendation = "買い"
    elif total_score > 0.1:
        recommendation = "やや買い"
    elif total_score < -0.3:
        recommendation = "売り"
    elif total_score < -0.1:
        recommendation = "やや売り"
    else:
        recommendation = "中立"

    # 信頼度（各スコアの一致度）
    score_values = list(component_scores.values())
    if score_values:
        # 全スコアが同じ方向なら信頼度が高い
        positive = sum(1 for s in score_values if s > 0.1)
        negative = sum(1 for s in score_values if s < -0.1)
        total = len(score_values)
        consistency = max(positive, negative) / total
        confidence = consistency
    else:
        confidence = 0.0

    return {
        "total_score": total_score,
        "recommendation": recommendation,
        "confidence": confidence,
        "component_scores": component_scores,
        "reasons": reasons if reasons else ["判断材料が不足しています"],
    }


def suggest_entry_exit(
    current_price: float,
    support_levels: list[float],
    resistance_levels: list[float],
    recommendation: str,
) -> dict:
    """エントリー・エグジットポイントを提案"""
    result = {
        "entry_price": None,
        "exit_price": None,
        "stop_loss": None,
        "take_profit": None,
    }

    # サポート・レジスタンスから近い水準を取得
    supports_below = [s for s in support_levels if s < current_price]
    resistances_above = [r for r in resistance_levels if r > current_price]

    if recommendation in ("買い", "やや買い"):
        # 直近のサポート付近でエントリー
        if supports_below:
            result["entry_price"] = max(supports_below)
            result["stop_loss"] = result["entry_price"] * 0.97  # -3%
        else:
            result["entry_price"] = current_price * 0.98
            result["stop_loss"] = current_price * 0.95

        # 直近のレジスタンスでエグジット
        if resistances_above:
            result["exit_price"] = min(resistances_above)
            result["take_profit"] = result["exit_price"]
        else:
            result["exit_price"] = current_price * 1.05
            result["take_profit"] = current_price * 1.05

    elif recommendation in ("売り", "やや売り"):
        # 直近のレジスタンス付近でエントリー（空売り）
        if resistances_above:
            result["entry_price"] = min(resistances_above)
            result["stop_loss"] = result["entry_price"] * 1.03
        else:
            result["entry_price"] = current_price * 1.02
            result["stop_loss"] = current_price * 1.05

        # 直近のサポートでエグジット
        if supports_below:
            result["exit_price"] = max(supports_below)
            result["take_profit"] = result["exit_price"]
        else:
            result["exit_price"] = current_price * 0.95
            result["take_profit"] = current_price * 0.95

    return result


def _calculate_technical_score(signals: list[dict]) -> float:
    """テクニカルシグナルからスコアを算出"""
    if not signals:
        return 0.0

    score_map = {"買い": 1.0, "中立": 0.0, "売り": -1.0, "注意": -0.2}
    scores = [score_map.get(s.get("signal"), 0.0) for s in signals]
    return sum(scores) / len(scores) if scores else 0.0


def _calculate_fundamental_score(evaluations: list[dict]) -> float:
    """ファンダメンタル評価からスコアを算出"""
    if not evaluations:
        return 0.0

    score_map = {"買い": 1.0, "中立": 0.0, "売り": -1.0, "注意": -0.3}
    scores = [score_map.get(e.get("signal"), 0.0) for e in evaluations]
    return sum(scores) / len(scores) if scores else 0.0

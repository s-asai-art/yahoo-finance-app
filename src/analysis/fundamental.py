"""ファンダメンタル分析モジュール"""


def evaluate_fundamental(data: dict | None) -> list[dict]:
    """ファンダメンタル指標の評価を生成"""
    if not data:
        return []

    evaluations = []

    # PER
    per = data.get("per")
    if per is not None:
        if per < 0:
            eval_text = "赤字"
            signal = "注意"
        elif per < 10:
            eval_text = "割安"
            signal = "買い"
        elif per < 20:
            eval_text = "適正"
            signal = "中立"
        elif per < 40:
            eval_text = "やや割高"
            signal = "注意"
        else:
            eval_text = "割高"
            signal = "売り"
        evaluations.append({
            "name": "PER",
            "value": f"{per:.1f}倍",
            "evaluation": eval_text,
            "signal": signal,
        })

    # PBR
    pbr = data.get("pbr")
    if pbr is not None:
        if pbr < 0:
            eval_text = "債務超過"
            signal = "注意"
        elif pbr < 1.0:
            eval_text = "割安"
            signal = "買い"
        elif pbr < 2.0:
            eval_text = "適正"
            signal = "中立"
        else:
            eval_text = "割高"
            signal = "売り"
        evaluations.append({
            "name": "PBR",
            "value": f"{pbr:.2f}倍",
            "evaluation": eval_text,
            "signal": signal,
        })

    # ROE
    roe = data.get("roe")
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct > 15:
            eval_text = "優秀"
            signal = "買い"
        elif roe_pct > 8:
            eval_text = "良好"
            signal = "中立"
        elif roe_pct > 0:
            eval_text = "低い"
            signal = "注意"
        else:
            eval_text = "赤字"
            signal = "売り"
        evaluations.append({
            "name": "ROE",
            "value": f"{roe_pct:.1f}%",
            "evaluation": eval_text,
            "signal": signal,
        })

    # ROA
    roa = data.get("roa")
    if roa is not None:
        roa_pct = roa * 100
        if roa_pct > 10:
            eval_text = "優秀"
            signal = "買い"
        elif roa_pct > 5:
            eval_text = "良好"
            signal = "中立"
        elif roa_pct > 0:
            eval_text = "低い"
            signal = "注意"
        else:
            eval_text = "赤字"
            signal = "売り"
        evaluations.append({
            "name": "ROA",
            "value": f"{roa_pct:.1f}%",
            "evaluation": eval_text,
            "signal": signal,
        })

    # 配当利回り
    div_yield = data.get("dividend_yield")
    if div_yield is not None:
        div_pct = div_yield * 100
        if div_pct > 4:
            eval_text = "高配当"
            signal = "買い"
        elif div_pct > 2:
            eval_text = "適正"
            signal = "中立"
        elif div_pct > 0:
            eval_text = "低配当"
            signal = "注意"
        else:
            eval_text = "無配"
            signal = "中立"
        evaluations.append({
            "name": "配当利回り",
            "value": f"{div_pct:.2f}%",
            "evaluation": eval_text,
            "signal": signal,
        })

    # 売上成長率
    rev_growth = data.get("revenue_growth")
    if rev_growth is not None:
        growth_pct = rev_growth * 100
        if growth_pct > 20:
            eval_text = "高成長"
            signal = "買い"
        elif growth_pct > 5:
            eval_text = "成長"
            signal = "中立"
        elif growth_pct > 0:
            eval_text = "微成長"
            signal = "中立"
        else:
            eval_text = "減収"
            signal = "売り"
        evaluations.append({
            "name": "売上成長率",
            "value": f"{growth_pct:.1f}%",
            "evaluation": eval_text,
            "signal": signal,
        })

    # 利益率
    profit_margin = data.get("profit_margin")
    if profit_margin is not None:
        margin_pct = profit_margin * 100
        if margin_pct > 15:
            eval_text = "高収益"
            signal = "買い"
        elif margin_pct > 5:
            eval_text = "適正"
            signal = "中立"
        elif margin_pct > 0:
            eval_text = "薄利"
            signal = "注意"
        else:
            eval_text = "赤字"
            signal = "売り"
        evaluations.append({
            "name": "純利益率",
            "value": f"{margin_pct:.1f}%",
            "evaluation": eval_text,
            "signal": signal,
        })

    # D/Eレシオ
    de_ratio = data.get("debt_to_equity")
    if de_ratio is not None:
        de_val = de_ratio / 100 if de_ratio > 10 else de_ratio
        if de_val < 0.5:
            eval_text = "健全"
            signal = "買い"
        elif de_val < 1.0:
            eval_text = "適正"
            signal = "中立"
        elif de_val < 2.0:
            eval_text = "やや高い"
            signal = "注意"
        else:
            eval_text = "高い"
            signal = "売り"
        evaluations.append({
            "name": "D/Eレシオ",
            "value": f"{de_val:.2f}",
            "evaluation": eval_text,
            "signal": signal,
        })

    return evaluations


def get_fundamental_score(evaluations: list[dict]) -> float:
    """ファンダメンタル評価スコアを算出（-1.0〜1.0）"""
    if not evaluations:
        return 0.0

    score_map = {"買い": 1.0, "中立": 0.0, "売り": -1.0, "注意": -0.3}
    scores = [score_map.get(e["signal"], 0.0) for e in evaluations]
    return sum(scores) / len(scores) if scores else 0.0

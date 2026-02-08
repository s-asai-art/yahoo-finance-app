"""リスク評価モジュール"""

import numpy as np
import pandas as pd


def calculate_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """ヒストリカルボラティリティを計算"""
    returns = df["Close"].pct_change().dropna()
    volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年率換算
    return volatility


def calculate_max_drawdown(df: pd.DataFrame) -> dict:
    """最大ドローダウンを計算"""
    prices = df["Close"]
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax

    max_dd = drawdown.min()
    max_dd_end_idx = drawdown.idxmin()

    # ドローダウン開始点を探す
    peak_prices = prices[:max_dd_end_idx]
    max_dd_start_idx = peak_prices.idxmax()

    return {
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd * 100,
        "start_date": max_dd_start_idx,
        "end_date": max_dd_end_idx,
        "drawdown_series": drawdown,
    }


def calculate_var(df: pd.DataFrame, confidence: float = 0.95, horizon: int = 1) -> dict:
    """VaR（Value at Risk）を計算

    Args:
        confidence: 信頼水準（0.95 = 95%）
        horizon: 保有期間（日数）
    """
    returns = df["Close"].pct_change().dropna()

    # ヒストリカルVaR
    historical_var = np.percentile(returns, (1 - confidence) * 100)

    # パラメトリックVaR（正規分布仮定）
    from scipy import stats
    mean = returns.mean()
    std = returns.std()
    parametric_var = stats.norm.ppf(1 - confidence, mean, std)

    # 保有期間調整
    historical_var_adj = historical_var * np.sqrt(horizon)
    parametric_var_adj = parametric_var * np.sqrt(horizon)

    # 現在の株価でのVaR金額（100株あたり）
    current_price = df["Close"].iloc[-1]
    var_amount = abs(historical_var_adj) * current_price * 100

    return {
        "historical_var": historical_var,
        "parametric_var": parametric_var,
        "historical_var_adj": historical_var_adj,
        "parametric_var_adj": parametric_var_adj,
        "confidence": confidence,
        "horizon": horizon,
        "var_amount_100shares": var_amount,
        "current_price": current_price,
    }


def calculate_beta(stock_df: pd.DataFrame, market_df: pd.DataFrame) -> float | None:
    """ベータ値を計算（日経平均との連動性）"""
    if stock_df is None or market_df is None:
        return None

    try:
        # 共通の日付でマージ
        stock_returns = stock_df["Close"].pct_change().dropna()
        market_returns = market_df["Close"].pct_change().dropna()

        # インデックスを揃える
        common_idx = stock_returns.index.intersection(market_returns.index)
        if len(common_idx) < 20:
            return None

        s_ret = stock_returns.loc[common_idx]
        m_ret = market_returns.loc[common_idx]

        covariance = np.cov(s_ret, m_ret)[0][1]
        market_variance = np.var(m_ret)

        if market_variance == 0:
            return None

        return covariance / market_variance
    except Exception:
        return None


def calculate_sharpe_ratio(df: pd.DataFrame, risk_free_rate: float = 0.001) -> float:
    """シャープレシオを計算（年率）"""
    returns = df["Close"].pct_change().dropna()
    annual_return = returns.mean() * 252
    annual_std = returns.std() * np.sqrt(252)

    if annual_std == 0:
        return 0.0

    return (annual_return - risk_free_rate) / annual_std


def get_risk_assessment(df: pd.DataFrame, market_df: pd.DataFrame = None) -> dict:
    """総合リスク評価を実施"""
    result = {}

    # ボラティリティ
    vol = calculate_volatility(df)
    current_vol = vol.iloc[-1] if not vol.empty and not pd.isna(vol.iloc[-1]) else None
    result["volatility"] = current_vol
    result["volatility_series"] = vol

    # 最大ドローダウン
    dd = calculate_max_drawdown(df)
    result["max_drawdown"] = dd

    # VaR
    try:
        var_data = calculate_var(df)
        result["var"] = var_data
    except Exception:
        result["var"] = None

    # ベータ値
    beta = calculate_beta(df, market_df)
    result["beta"] = beta

    # シャープレシオ
    sharpe = calculate_sharpe_ratio(df)
    result["sharpe_ratio"] = sharpe

    # リスクスコア（0-100）
    risk_score = _calculate_risk_score(current_vol, dd["max_drawdown"], beta, sharpe)
    result["risk_score"] = risk_score
    result["risk_level"] = _risk_level(risk_score)

    return result


def _calculate_risk_score(volatility, max_dd, beta, sharpe) -> float:
    """リスクスコアを算出（0=低リスク, 100=高リスク）"""
    score = 50.0  # 基準

    # ボラティリティ（年率30%以上は高リスク）
    if volatility is not None:
        if volatility > 0.5:
            score += 20
        elif volatility > 0.3:
            score += 10
        elif volatility < 0.15:
            score -= 10

    # 最大ドローダウン
    if max_dd is not None:
        if max_dd < -0.3:
            score += 15
        elif max_dd < -0.2:
            score += 10
        elif max_dd > -0.1:
            score -= 5

    # ベータ値
    if beta is not None:
        if beta > 1.5:
            score += 10
        elif beta > 1.2:
            score += 5
        elif beta < 0.8:
            score -= 5

    # シャープレシオ
    if sharpe is not None:
        if sharpe < 0:
            score += 10
        elif sharpe > 1.0:
            score -= 10

    return max(0, min(100, score))


def _risk_level(score: float) -> str:
    """リスクスコアからリスクレベルを判定"""
    if score >= 75:
        return "非常に高い"
    elif score >= 60:
        return "高い"
    elif score >= 40:
        return "中程度"
    elif score >= 25:
        return "低い"
    else:
        return "非常に低い"

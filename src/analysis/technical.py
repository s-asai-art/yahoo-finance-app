"""テクニカル分析モジュール"""

import numpy as np
import pandas as pd

from config.settings import TECHNICAL_DEFAULTS


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """移動平均線を追加"""
    df = df.copy()
    for period in [
        TECHNICAL_DEFAULTS["ma_short"],
        TECHNICAL_DEFAULTS["ma_medium"],
        TECHNICAL_DEFAULTS["ma_long"],
        TECHNICAL_DEFAULTS["ma_very_long"],
    ]:
        df[f"MA_{period}"] = df["Close"].rolling(window=period).mean()
    return df


def add_bollinger_bands(df: pd.DataFrame) -> pd.DataFrame:
    """ボリンジャーバンドを追加"""
    df = df.copy()
    period = TECHNICAL_DEFAULTS["bb_period"]
    std_dev = TECHNICAL_DEFAULTS["bb_std"]

    df["BB_Middle"] = df["Close"].rolling(window=period).mean()
    rolling_std = df["Close"].rolling(window=period).std()
    df["BB_Upper"] = df["BB_Middle"] + (rolling_std * std_dev)
    df["BB_Lower"] = df["BB_Middle"] - (rolling_std * std_dev)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
    return df


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """RSIを追加"""
    df = df.copy()
    period = TECHNICAL_DEFAULTS["rsi_period"]

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """MACD（移動平均収束拡散法）を追加"""
    df = df.copy()
    fast = TECHNICAL_DEFAULTS["macd_fast"]
    slow = TECHNICAL_DEFAULTS["macd_slow"]
    signal = TECHNICAL_DEFAULTS["macd_signal"]

    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]
    return df


def add_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """ストキャスティクスを追加"""
    df = df.copy()
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()

    denom = high_max - low_min
    denom = denom.replace(0, np.nan)
    df["Stoch_K"] = ((df["Close"] - low_min) / denom) * 100
    df["Stoch_D"] = df["Stoch_K"].rolling(window=d_period).mean()
    return df


def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """一目均衡表を追加"""
    df = df.copy()

    # 転換線（9日）
    high_9 = df["High"].rolling(window=9).max()
    low_9 = df["Low"].rolling(window=9).min()
    df["Ichimoku_Tenkan"] = (high_9 + low_9) / 2

    # 基準線（26日）
    high_26 = df["High"].rolling(window=26).max()
    low_26 = df["Low"].rolling(window=26).min()
    df["Ichimoku_Kijun"] = (high_26 + low_26) / 2

    # 先行スパン1（26日先）
    df["Ichimoku_SpanA"] = ((df["Ichimoku_Tenkan"] + df["Ichimoku_Kijun"]) / 2).shift(26)

    # 先行スパン2（52日の中間値を26日先）
    high_52 = df["High"].rolling(window=52).max()
    low_52 = df["Low"].rolling(window=52).min()
    df["Ichimoku_SpanB"] = ((high_52 + low_52) / 2).shift(26)

    # 遅行スパン（26日前）
    df["Ichimoku_Chikou"] = df["Close"].shift(-26)

    return df


def add_volume_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """出来高分析を追加"""
    df = df.copy()
    df["Volume_MA_5"] = df["Volume"].rolling(window=5).mean()
    df["Volume_MA_25"] = df["Volume"].rolling(window=25).mean()
    df["Volume_Ratio"] = df["Volume"] / df["Volume_MA_25"].replace(0, np.nan)
    return df


def detect_golden_dead_cross(df: pd.DataFrame) -> list[dict]:
    """ゴールデンクロス・デッドクロス検出"""
    signals = []
    if "MA_5" not in df.columns or "MA_25" not in df.columns:
        df = add_moving_averages(df)

    ma_short = df["MA_5"]
    ma_long = df["MA_25"]

    for i in range(1, len(df)):
        if pd.isna(ma_short.iloc[i]) or pd.isna(ma_long.iloc[i]):
            continue
        if pd.isna(ma_short.iloc[i - 1]) or pd.isna(ma_long.iloc[i - 1]):
            continue

        # ゴールデンクロス
        if ma_short.iloc[i - 1] < ma_long.iloc[i - 1] and ma_short.iloc[i] >= ma_long.iloc[i]:
            signals.append({
                "date": df.index[i],
                "type": "golden_cross",
                "label": "ゴールデンクロス",
                "signal": "買い",
            })
        # デッドクロス
        elif ma_short.iloc[i - 1] > ma_long.iloc[i - 1] and ma_short.iloc[i] <= ma_long.iloc[i]:
            signals.append({
                "date": df.index[i],
                "type": "dead_cross",
                "label": "デッドクロス",
                "signal": "売り",
            })

    return signals


def detect_support_resistance(df: pd.DataFrame, window: int = 20, threshold: float = 0.02) -> dict:
    """サポート・レジスタンスライン自動検出"""
    if len(df) < window:
        return {"support": [], "resistance": []}

    supports = []
    resistances = []

    for i in range(window, len(df) - window):
        # ローカルミニマム（サポート）
        if df["Low"].iloc[i] == df["Low"].iloc[i - window:i + window + 1].min():
            level = df["Low"].iloc[i]
            # 重複チェック
            if not any(abs(s - level) / level < threshold for s in supports):
                supports.append(level)

        # ローカルマキシマム（レジスタンス）
        if df["High"].iloc[i] == df["High"].iloc[i - window:i + window + 1].max():
            level = df["High"].iloc[i]
            if not any(abs(r - level) / level < threshold for r in resistances):
                resistances.append(level)

    # 直近の価格に近いものを優先してソート
    current_price = df["Close"].iloc[-1]
    supports = sorted(supports, key=lambda x: abs(x - current_price))[:5]
    resistances = sorted(resistances, key=lambda x: abs(x - current_price))[:5]

    return {"support": sorted(supports), "resistance": sorted(resistances)}


def get_all_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """全テクニカル指標を一括計算"""
    df = add_moving_averages(df)
    df = add_bollinger_bands(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_stochastic(df)
    df = add_ichimoku(df)
    df = add_volume_analysis(df)
    return df


def get_technical_signals(df: pd.DataFrame) -> list[dict]:
    """テクニカル指標のシグナルを生成"""
    if df is None or df.empty:
        return []

    signals = []
    last = df.iloc[-1]

    # RSI
    if "RSI" in df.columns and not pd.isna(last.get("RSI")):
        rsi = last["RSI"]
        if rsi < 30:
            signals.append({"name": "RSI", "value": f"{rsi:.1f}", "signal": "買い", "reason": "RSI 30以下（売られすぎ）"})
        elif rsi > 70:
            signals.append({"name": "RSI", "value": f"{rsi:.1f}", "signal": "売り", "reason": "RSI 70以上（買われすぎ）"})
        else:
            signals.append({"name": "RSI", "value": f"{rsi:.1f}", "signal": "中立", "reason": "RSI 正常範囲"})

    # MACD
    if "MACD" in df.columns and "MACD_Signal" in df.columns:
        macd = last.get("MACD")
        macd_signal = last.get("MACD_Signal")
        if not pd.isna(macd) and not pd.isna(macd_signal):
            if macd > macd_signal:
                signals.append({"name": "MACD", "value": f"{macd:.2f}", "signal": "買い", "reason": "MACDがシグナル線上方"})
            else:
                signals.append({"name": "MACD", "value": f"{macd:.2f}", "signal": "売り", "reason": "MACDがシグナル線下方"})

    # ボリンジャーバンド
    if "BB_Upper" in df.columns and "BB_Lower" in df.columns:
        close = last["Close"]
        bb_upper = last.get("BB_Upper")
        bb_lower = last.get("BB_Lower")
        if not pd.isna(bb_upper) and not pd.isna(bb_lower):
            if close > bb_upper:
                signals.append({"name": "ボリンジャーバンド", "value": f"上限突破", "signal": "売り", "reason": "上限バンド超え"})
            elif close < bb_lower:
                signals.append({"name": "ボリンジャーバンド", "value": f"下限突破", "signal": "買い", "reason": "下限バンド割れ"})
            else:
                signals.append({"name": "ボリンジャーバンド", "value": "範囲内", "signal": "中立", "reason": "バンド内推移"})

    # 移動平均線トレンド
    if "MA_5" in df.columns and "MA_25" in df.columns:
        ma5 = last.get("MA_5")
        ma25 = last.get("MA_25")
        if not pd.isna(ma5) and not pd.isna(ma25):
            if ma5 > ma25:
                signals.append({"name": "移動平均線(5/25)", "value": "上昇トレンド", "signal": "買い", "reason": "短期MAが長期MA上方"})
            else:
                signals.append({"name": "移動平均線(5/25)", "value": "下降トレンド", "signal": "売り", "reason": "短期MAが長期MA下方"})

    # ストキャスティクス
    if "Stoch_K" in df.columns and "Stoch_D" in df.columns:
        stoch_k = last.get("Stoch_K")
        stoch_d = last.get("Stoch_D")
        if not pd.isna(stoch_k) and not pd.isna(stoch_d):
            if stoch_k < 20 and stoch_d < 20:
                signals.append({"name": "ストキャスティクス", "value": f"%K={stoch_k:.1f}", "signal": "買い", "reason": "売られすぎゾーン"})
            elif stoch_k > 80 and stoch_d > 80:
                signals.append({"name": "ストキャスティクス", "value": f"%K={stoch_k:.1f}", "signal": "売り", "reason": "買われすぎゾーン"})
            else:
                signals.append({"name": "ストキャスティクス", "value": f"%K={stoch_k:.1f}", "signal": "中立", "reason": "中間ゾーン"})

    # 出来高
    if "Volume_Ratio" in df.columns:
        vol_ratio = last.get("Volume_Ratio")
        if not pd.isna(vol_ratio):
            if vol_ratio > 2.0:
                signals.append({"name": "出来高", "value": f"{vol_ratio:.1f}倍", "signal": "注意", "reason": "出来高急増"})
            elif vol_ratio < 0.5:
                signals.append({"name": "出来高", "value": f"{vol_ratio:.1f}倍", "signal": "注意", "reason": "出来高過少"})
            else:
                signals.append({"name": "出来高", "value": f"{vol_ratio:.1f}倍", "signal": "中立", "reason": "通常水準"})

    return signals

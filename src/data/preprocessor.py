"""データ前処理モジュール"""

import numpy as np
import pandas as pd


def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
    """株価データのクリーニング"""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # 欠損値処理
    df = df.dropna(subset=["Close"])
    df["Open"] = df["Open"].fillna(df["Close"])
    df["High"] = df["High"].fillna(df["Close"])
    df["Low"] = df["Low"].fillna(df["Close"])
    df["Volume"] = df["Volume"].fillna(0)

    # 異常値除去（前日比±50%以上の変動を除外）
    returns = df["Close"].pct_change()
    mask = returns.abs() < 0.5
    mask.iloc[0] = True
    df = df[mask]

    return df


def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    """リターンを計算"""
    df = df.copy()
    df["Daily_Return"] = df["Close"].pct_change()
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["Cumulative_Return"] = (1 + df["Daily_Return"]).cumprod() - 1
    return df


def normalize_series(series: pd.Series) -> pd.Series:
    """0-1に正規化"""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(0.5, index=series.index)
    return (series - min_val) / (max_val - min_val)


def prepare_ml_features(df: pd.DataFrame, lookback: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """機械学習用特徴量を準備する

    Returns:
        X: 特徴量 (n_samples, lookback, n_features)
        y: ターゲット (n_samples,) - 翌日のリターン
    """
    if df is None or len(df) < lookback + 10:
        return np.array([]), np.array([])

    df = df.copy()

    # 特徴量
    df["Return"] = df["Close"].pct_change()
    df["Volume_Change"] = df["Volume"].pct_change()
    df["High_Low_Ratio"] = (df["High"] - df["Low"]) / df["Close"]
    df["Close_Open_Ratio"] = (df["Close"] - df["Open"]) / df["Open"]

    # 移動平均乖離率
    for w in [5, 25, 75]:
        ma = df["Close"].rolling(window=w).mean()
        df[f"MA_{w}_Deviation"] = (df["Close"] - ma) / ma

    # ボラティリティ
    df["Volatility_5"] = df["Return"].rolling(window=5).std()
    df["Volatility_20"] = df["Return"].rolling(window=20).std()

    # RSI
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # ターゲット：翌日リターン
    df["Target"] = df["Return"].shift(-1)

    # 欠損値除去
    feature_cols = [
        "Return", "Volume_Change", "High_Low_Ratio", "Close_Open_Ratio",
        "MA_5_Deviation", "MA_25_Deviation", "MA_75_Deviation",
        "Volatility_5", "Volatility_20", "RSI",
    ]
    df = df.dropna(subset=feature_cols + ["Target"])

    if len(df) < lookback + 1:
        return np.array([]), np.array([])

    # シーケンスデータ作成
    features = df[feature_cols].values
    targets = df["Target"].values

    X, y = [], []
    for i in range(lookback, len(features)):
        X.append(features[i - lookback:i])
        y.append(targets[i])

    return np.array(X), np.array(y)

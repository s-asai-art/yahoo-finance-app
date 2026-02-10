"""トレンド分類モデル（Random Forest）"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrendClassifier:
    """トレンド分類器（上昇/下降/横ばい）"""

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
        )
        self.is_trained = False
        self.accuracy = None

    def _prepare_features(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """特徴量とラベルを準備"""
        data = df.copy()

        # 特徴量
        data["Return_1"] = data["Close"].pct_change(1)
        data["Return_5"] = data["Close"].pct_change(5)
        data["Return_10"] = data["Close"].pct_change(10)

        data["MA_5"] = data["Close"].rolling(5).mean()
        data["MA_25"] = data["Close"].rolling(25).mean()
        data["MA_5_Dev"] = (data["Close"] - data["MA_5"]) / data["MA_5"]
        data["MA_25_Dev"] = (data["Close"] - data["MA_25"]) / data["MA_25"]

        data["Vol_5"] = data["Return_1"].rolling(5).std()
        data["Vol_20"] = data["Return_1"].rolling(20).std()

        data["Volume_Ratio"] = data["Volume"] / data["Volume"].rolling(20).mean()

        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        data["RSI"] = 100 - (100 / (1 + rs))

        data["High_Low_Range"] = (data["High"] - data["Low"]) / data["Close"]

        # ラベル: 5日後のリターンで分類
        future_return = data["Close"].shift(-5) / data["Close"] - 1
        data["Label"] = 1  # 横ばい
        data.loc[future_return > 0.02, "Label"] = 2  # 上昇
        data.loc[future_return < -0.02, "Label"] = 0  # 下降

        feature_cols = [
            "Return_1", "Return_5", "Return_10",
            "MA_5_Dev", "MA_25_Dev",
            "Vol_5", "Vol_20",
            "Volume_Ratio", "RSI", "High_Low_Range",
        ]

        data = data.dropna(subset=feature_cols + ["Label"])
        # 未来のデータを使ったラベルの最後5行は除外
        data = data.iloc[:-5]

        X = data[feature_cols].values
        y = data["Label"].values

        return X, y

    def train(self, df: pd.DataFrame) -> bool:
        """モデルを学習する"""
        try:
            if df is None or len(df) < 100:
                return False

            X, y = self._prepare_features(df)
            if len(X) < 50:
                return False

            # 交差検証
            scores = cross_val_score(self.model, X, y, cv=5, scoring="accuracy")
            self.accuracy = scores.mean()

            # 全データで学習
            self.model.fit(X, y)
            self.is_trained = True

            logger.info(f"トレンド分類モデル学習完了: 精度={self.accuracy:.3f}")
            return True
        except Exception as e:
            logger.error(f"トレンド分類モデル学習エラー: {e}")
            return False

    def predict(self, df: pd.DataFrame) -> dict | None:
        """現在のトレンドを予測する"""
        if not self.is_trained or df is None or len(df) < 30:
            return None

        try:
            X, _ = self._prepare_features(df)
            if len(X) == 0:
                return None

            # 最新データで予測
            latest = X[-1:] if len(X) > 0 else None
            if latest is None:
                return None

            pred = self.model.predict(latest)[0]
            proba = self.model.predict_proba(latest)[0]

            label_map = {0: "下降", 1: "横ばい", 2: "上昇"}

            return {
                "trend": label_map.get(pred, "不明"),
                "confidence": float(max(proba)),
                "probabilities": {
                    "下降": float(proba[0]) if len(proba) > 0 else 0,
                    "横ばい": float(proba[1]) if len(proba) > 1 else 0,
                    "上昇": float(proba[2]) if len(proba) > 2 else 0,
                },
                "model_accuracy": self.accuracy,
            }
        except Exception as e:
            logger.error(f"トレンド予測エラー: {e}")
            return None

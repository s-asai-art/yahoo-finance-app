"""価格予測モデル（LSTMベース）"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PricePredictor:
    """株価予測クラス（線形回帰 + ARIMAライクな簡易モデル）"""

    def __init__(self):
        self.scaler = MinMaxScaler()
        self.is_trained = False
        self._weights = None
        self._lookback = 30

    def train(self, df: pd.DataFrame) -> bool:
        """モデルを学習する"""
        try:
            if df is None or len(df) < self._lookback + 20:
                return False

            closes = df["Close"].values.reshape(-1, 1)
            self.scaler.fit(closes)
            scaled = self.scaler.transform(closes).flatten()

            # 簡易的な重み付き移動平均ベースの予測モデル
            # 直近データほど重みを大きくする
            X, y = [], []
            for i in range(self._lookback, len(scaled) - 1):
                X.append(scaled[i - self._lookback:i])
                y.append(scaled[i])

            X = np.array(X)
            y = np.array(y)

            # 重み付き線形回帰
            # 指数減衰の重み
            weights = np.exp(np.linspace(-2, 0, self._lookback))
            weights = weights / weights.sum()

            # 各時点での重み付き平均と実際値の関係を学習
            predictions = np.array([np.dot(x, weights) for x in X])
            if np.std(predictions) > 0:
                # 線形補正
                slope = np.cov(y, predictions)[0][1] / np.var(predictions)
                intercept = np.mean(y) - slope * np.mean(predictions)
                self._weights = weights
                self._slope = slope
                self._intercept = intercept
            else:
                self._weights = weights
                self._slope = 1.0
                self._intercept = 0.0

            self.is_trained = True
            return True
        except Exception as e:
            logger.error(f"モデル学習エラー: {e}")
            return False

    def predict(self, df: pd.DataFrame, days: int = 5) -> dict | None:
        """将来の価格を予測する

        Returns:
            dict with keys: predictions, confidence_upper, confidence_lower, dates
        """
        if not self.is_trained or df is None or len(df) < self._lookback:
            return None

        try:
            closes = df["Close"].values.reshape(-1, 1)
            scaled = self.scaler.transform(closes).flatten()
            recent = scaled[-self._lookback:].copy()

            # リターンのボラティリティ推定（信頼区間用）
            returns = np.diff(closes.flatten()) / closes.flatten()[:-1]
            vol = np.std(returns[-60:]) if len(returns) >= 60 else np.std(returns)

            predictions = []
            for _ in range(days):
                pred_scaled = np.dot(recent, self._weights) * self._slope + self._intercept
                predictions.append(pred_scaled)
                recent = np.append(recent[1:], pred_scaled)

            # スケールを戻す
            pred_prices = self.scaler.inverse_transform(
                np.array(predictions).reshape(-1, 1)
            ).flatten()

            # 信頼区間（ボラティリティベース）
            last_price = df["Close"].iloc[-1]
            confidence_upper = []
            confidence_lower = []
            for i, price in enumerate(pred_prices):
                std = last_price * vol * np.sqrt(i + 1) * 1.96  # 95%信頼区間
                confidence_upper.append(price + std)
                confidence_lower.append(price - std)

            # 予測日付
            last_date = df.index[-1]
            dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=days)

            return {
                "predictions": pred_prices.tolist(),
                "confidence_upper": confidence_upper,
                "confidence_lower": confidence_lower,
                "dates": dates.tolist(),
                "last_actual_price": last_price,
                "last_actual_date": last_date,
            }
        except Exception as e:
            logger.error(f"予測エラー: {e}")
            return None

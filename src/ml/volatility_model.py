"""ボラティリティ予測モデル"""

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class VolatilityPredictor:
    """EWMA（指数加重移動平均）ベースのボラティリティ予測"""

    def __init__(self, lambda_param: float = 0.94):
        self.lambda_param = lambda_param
        self.is_trained = False
        self._current_var = None

    def train(self, df: pd.DataFrame) -> bool:
        """EWMAボラティリティモデルを適用"""
        try:
            if df is None or len(df) < 30:
                return False

            returns = df["Close"].pct_change().dropna()

            # EWMA分散を計算
            var = returns.iloc[0] ** 2
            variances = [var]

            for r in returns.iloc[1:]:
                var = self.lambda_param * var + (1 - self.lambda_param) * r ** 2
                variances.append(var)

            self._current_var = var
            self._variance_series = pd.Series(
                variances,
                index=returns.index,
            )
            self.is_trained = True
            return True
        except Exception as e:
            logger.error(f"ボラティリティモデル学習エラー: {e}")
            return False

    def predict(self, days: int = 5) -> dict | None:
        """将来のボラティリティを予測"""
        if not self.is_trained or self._current_var is None:
            return None

        try:
            # EWMAでは将来のボラティリティ＝現在のボラティリティ
            daily_vol = np.sqrt(self._current_var)
            annual_vol = daily_vol * np.sqrt(252)

            # 各日の予測ボラティリティ
            predicted_vols = []
            var = self._current_var
            for _ in range(days):
                predicted_vols.append(np.sqrt(var) * np.sqrt(252))
                # EWMAの予測: 分散は減衰しない（一定を仮定）
                var = self.lambda_param * var + (1 - self.lambda_param) * self._current_var

            return {
                "current_daily_vol": daily_vol,
                "current_annual_vol": annual_vol,
                "predicted_annual_vols": predicted_vols,
                "variance_series": self._variance_series,
            }
        except Exception as e:
            logger.error(f"ボラティリティ予測エラー: {e}")
            return None

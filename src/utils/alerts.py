"""アラート機能モジュール"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Alert:
    """アラート情報"""
    alert_type: str  # "price_upper", "price_lower", "volume", "sentiment", "technical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    stock_code: str = ""
    triggered: bool = False


class AlertManager:
    """アラート管理クラス"""

    def __init__(self):
        self.alerts: list[Alert] = []
        self.settings: dict = {
            "price_upper": None,
            "price_lower": None,
            "volume_threshold": None,
            "sentiment_alert": False,
        }

    def check_price_alerts(self, current_price: float) -> list[Alert]:
        """価格アラートのチェック"""
        triggered = []

        if self.settings["price_upper"] and current_price >= self.settings["price_upper"]:
            alert = Alert(
                alert_type="price_upper",
                message=f"株価が上限 ¥{self.settings['price_upper']:,.0f} に到達: ¥{current_price:,.0f}",
            )
            triggered.append(alert)

        if self.settings["price_lower"] and current_price <= self.settings["price_lower"]:
            alert = Alert(
                alert_type="price_lower",
                message=f"株価が下限 ¥{self.settings['price_lower']:,.0f} に到達: ¥{current_price:,.0f}",
            )
            triggered.append(alert)

        self.alerts.extend(triggered)
        return triggered

    def check_volume_alert(self, current_volume: float, avg_volume: float) -> list[Alert]:
        """出来高急増アラートのチェック"""
        triggered = []
        multiplier = self.settings.get("volume_threshold", 2.0)
        if multiplier and current_volume > avg_volume * multiplier:
            alert = Alert(
                alert_type="volume",
                message=f"出来高急増: {current_volume:,.0f} (平均の{current_volume/avg_volume:.1f}倍)",
            )
            triggered.append(alert)
            self.alerts.extend(triggered)
        return triggered

    def check_sentiment_alert(self, score: float, prev_score: float) -> list[Alert]:
        """センチメント急変アラートのチェック"""
        triggered = []
        if self.settings.get("sentiment_alert") and abs(score - prev_score) > 0.3:
            direction = "改善" if score > prev_score else "悪化"
            alert = Alert(
                alert_type="sentiment",
                message=f"センチメント急変({direction}): {prev_score:.2f} → {score:.2f}",
            )
            triggered.append(alert)
            self.alerts.extend(triggered)
        return triggered

    def add_technical_alert(self, signal_name: str, signal_type: str):
        """テクニカルシグナルのアラート追加"""
        alert = Alert(
            alert_type="technical",
            message=f"テクニカルシグナル: {signal_name} ({signal_type})",
        )
        self.alerts.append(alert)
        return alert

    def get_recent_alerts(self, count: int = 10) -> list[Alert]:
        """最近のアラートを取得"""
        return sorted(self.alerts, key=lambda a: a.timestamp, reverse=True)[:count]

    def clear_alerts(self):
        """アラートをクリア"""
        self.alerts.clear()

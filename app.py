"""Yahoo!ファイナンス リアルタイム株価分析Webアプリケーション"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

from config.settings import (
    CHART_PERIODS,
    DEFAULT_FAVORITES,
    DEFAULT_HISTORY_PERIOD,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_STOCK_CODE,
    REFRESH_INTERVALS,
)
from src.analysis.fundamental import evaluate_fundamental, get_fundamental_score
from src.analysis.risk import get_risk_assessment
from src.analysis.sentiment import analyze_posts_sentiment, extract_keywords
from src.analysis.technical import (
    detect_golden_dead_cross,
    detect_support_resistance,
    get_all_technical_indicators,
    get_technical_signals,
)
from src.data.fetcher import (
    fetch_board_posts,
    fetch_fundamental_data,
    fetch_historical_data,
    fetch_nikkei225_data,
    fetch_realtime_price,
)
from src.data.preprocessor import clean_price_data
from src.decision.engine import calculate_investment_score, suggest_entry_exit
from src.ml.price_predictor import PricePredictor
from src.ml.trend_classifier import TrendClassifier
from src.ml.volatility_model import VolatilityPredictor
from src.utils.alerts import AlertManager

# --- ページ設定 ---
st.set_page_config(
    page_title="株価分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- カスタムCSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #FF6B6B;
        margin-bottom: 0.5rem;
    }
    .price-up { color: #FF4444; font-weight: bold; }
    .price-down { color: #4444FF; font-weight: bold; }
    .price-flat { color: #888888; }
    .metric-card {
        background-color: #1E1E2E;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #333;
    }
    .signal-buy { background-color: #1a3a1a; color: #44ff44; padding: 3px 8px; border-radius: 4px; }
    .signal-sell { background-color: #3a1a1a; color: #ff4444; padding: 3px 8px; border-radius: 4px; }
    .signal-neutral { background-color: #2a2a1a; color: #ffff44; padding: 3px 8px; border-radius: 4px; }
    .disclaimer {
        background-color: #2a1a1a;
        border: 1px solid #ff6b6b;
        border-radius: 8px;
        padding: 1rem;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# --- セッション状態初期化 ---
def init_session_state():
    defaults = {
        "stock_code": DEFAULT_STOCK_CODE,
        "refresh_interval": DEFAULT_REFRESH_INTERVAL,
        "chart_period": DEFAULT_HISTORY_PERIOD,
        "show_ma": True,
        "show_bb": True,
        "show_ichimoku": False,
        "show_volume": True,
        "favorites": list(DEFAULT_FAVORITES),
        "recent_stocks": [],
        "alert_manager": AlertManager(),
        "price_predictor": PricePredictor(),
        "trend_classifier": TrendClassifier(),
        "volatility_model": VolatilityPredictor(),
        "models_trained": False,
        "prev_sentiment_score": 0.0,
        "dark_mode": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# --- 自動更新 ---
refresh_ms = st.session_state.refresh_interval * 1000
st_autorefresh(interval=refresh_ms, key="auto_refresh")


# --- サイドバー ---
def render_sidebar():
    with st.sidebar:
        st.markdown("## 📊 株価分析ダッシュボード")

        # 免責事項
        st.markdown(
            '<div class="disclaimer">'
            "⚠️ <b>免責事項</b>: 本アプリの情報は投資助言ではありません。"
            "投資判断は自己責任でお願いします。予測は参考情報です。"
            "</div>",
            unsafe_allow_html=True,
        )

        # 銘柄検索
        st.markdown("### 🔍 銘柄選択")
        code_input = st.text_input(
            "銘柄コード",
            value=st.session_state.stock_code,
            placeholder="例: 7203",
            help="日本株の銘柄コードを入力してください",
        )
        if code_input != st.session_state.stock_code:
            st.session_state.stock_code = code_input.strip().replace(".T", "")
            st.session_state.models_trained = False
            # 最近見た銘柄に追加
            recent = st.session_state.recent_stocks
            if code_input not in recent:
                recent.insert(0, code_input)
                st.session_state.recent_stocks = recent[:10]

        # お気に入り銘柄
        st.markdown("### ⭐ お気に入り")
        for code, name in st.session_state.favorites:
            if st.button(f"{code} - {name}", key=f"fav_{code}", use_container_width=True):
                st.session_state.stock_code = code
                st.session_state.models_trained = False
                st.rerun()

        # 最近見た銘柄
        if st.session_state.recent_stocks:
            st.markdown("### 🕐 最近の銘柄")
            for code in st.session_state.recent_stocks[:5]:
                if st.button(code, key=f"recent_{code}", use_container_width=True):
                    st.session_state.stock_code = code
                    st.session_state.models_trained = False
                    st.rerun()

        st.markdown("---")

        # 表示設定
        st.markdown("### ⚙️ 表示設定")
        interval_label = st.selectbox(
            "更新間隔",
            options=list(REFRESH_INTERVALS.keys()),
            index=list(REFRESH_INTERVALS.values()).index(st.session_state.refresh_interval)
            if st.session_state.refresh_interval in REFRESH_INTERVALS.values()
            else 1,
        )
        st.session_state.refresh_interval = REFRESH_INTERVALS[interval_label]

        period_label = st.selectbox(
            "チャート期間",
            options=list(CHART_PERIODS.keys()),
            index=3,  # 1年
        )
        st.session_state.chart_period = CHART_PERIODS[period_label]

        st.markdown("### 📈 表示指標")
        st.session_state.show_ma = st.checkbox("移動平均線", value=st.session_state.show_ma)
        st.session_state.show_bb = st.checkbox("ボリンジャーバンド", value=st.session_state.show_bb)
        st.session_state.show_ichimoku = st.checkbox("一目均衡表", value=st.session_state.show_ichimoku)
        st.session_state.show_volume = st.checkbox("出来高", value=st.session_state.show_volume)

        st.markdown("---")

        # アラート設定
        st.markdown("### 🔔 アラート設定")
        alert_mgr = st.session_state.alert_manager
        price_upper = st.number_input("上限価格", min_value=0.0, value=0.0, step=100.0)
        if price_upper > 0:
            alert_mgr.settings["price_upper"] = price_upper
        price_lower = st.number_input("下限価格", min_value=0.0, value=0.0, step=100.0)
        if price_lower > 0:
            alert_mgr.settings["price_lower"] = price_lower
        alert_mgr.settings["sentiment_alert"] = st.checkbox("センチメント急変通知", value=False)


render_sidebar()


# --- メインコンテンツ ---
code = st.session_state.stock_code

# データ取得
with st.spinner("データ取得中..."):
    realtime = fetch_realtime_price(code)
    hist_df = fetch_historical_data(code, period=st.session_state.chart_period)
    fundamental = fetch_fundamental_data(code)
    board_posts = fetch_board_posts(code, pages=2)

# データ取得失敗時
if realtime is None and (hist_df is None or hist_df.empty):
    st.error(f"銘柄コード {code} のデータを取得できませんでした。銘柄コードを確認してください。")
    st.stop()

# データ前処理
if hist_df is not None and not hist_df.empty:
    hist_df = clean_price_data(hist_df)
    hist_df = get_all_technical_indicators(hist_df)

# --- ヘッダー: 株価表示 ---
stock_name = realtime.get("name", code) if realtime else code
st.markdown(f'<div class="main-header">{stock_name} ({code})</div>', unsafe_allow_html=True)

# 価格情報メトリクス
if realtime:
    price = realtime.get("price")
    change = realtime.get("change")
    change_pct = realtime.get("change_percent")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        if price is not None:
            st.metric("現在値", f"¥{price:,.0f}" if price else "---",
                      delta=f"{change:+,.0f} ({change_pct:+.2f}%)" if change else None)
    with col2:
        st.metric("始値", f"¥{realtime.get('open', 0):,.0f}" if realtime.get("open") else "---")
    with col3:
        st.metric("高値", f"¥{realtime.get('high', 0):,.0f}" if realtime.get("high") else "---")
    with col4:
        st.metric("安値", f"¥{realtime.get('low', 0):,.0f}" if realtime.get("low") else "---")
    with col5:
        vol = realtime.get("volume")
        st.metric("出来高", f"{vol:,.0f}" if vol else "---")
    with col6:
        mcap = realtime.get("market_cap")
        if mcap:
            if mcap >= 1e12:
                st.metric("時価総額", f"¥{mcap / 1e12:.1f}兆")
            else:
                st.metric("時価総額", f"¥{mcap / 1e8:.0f}億")
        else:
            st.metric("時価総額", "---")

    # アラートチェック
    if price:
        alert_mgr = st.session_state.alert_manager
        price_alerts = alert_mgr.check_price_alerts(float(price))
        for alert in price_alerts:
            st.warning(f"🔔 {alert.message}")

st.markdown("---")

# === メインレイアウト ===
# 上部: チャート + 投資判断サマリー
chart_col, summary_col = st.columns([3, 1])

# --- チャートエリア ---
with chart_col:
    st.markdown("### 📈 チャート")

    if hist_df is not None and not hist_df.empty:
        # サブプロット構成
        row_heights = [0.6, 0.15, 0.15, 0.1] if st.session_state.show_volume else [0.7, 0.15, 0.15]
        n_rows = 4 if st.session_state.show_volume else 3

        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=("", "MACD", "RSI", "出来高") if st.session_state.show_volume
            else ("", "MACD", "RSI"),
        )

        # ローソク足
        fig.add_trace(go.Candlestick(
            x=hist_df.index,
            open=hist_df["Open"],
            high=hist_df["High"],
            low=hist_df["Low"],
            close=hist_df["Close"],
            name="株価",
            increasing_line_color="#FF4444",
            decreasing_line_color="#4488FF",
            increasing_fillcolor="#FF4444",
            decreasing_fillcolor="#4488FF",
        ), row=1, col=1)

        # 移動平均線
        if st.session_state.show_ma:
            colors = {"MA_5": "#FFD700", "MA_25": "#FF6B6B", "MA_75": "#4488FF", "MA_200": "#44FF44"}
            for ma_name, color in colors.items():
                if ma_name in hist_df.columns:
                    fig.add_trace(go.Scatter(
                        x=hist_df.index, y=hist_df[ma_name],
                        name=ma_name.replace("_", ""), line=dict(color=color, width=1),
                        opacity=0.8,
                    ), row=1, col=1)

        # ボリンジャーバンド
        if st.session_state.show_bb and "BB_Upper" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["BB_Upper"],
                name="BB上限", line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["BB_Lower"],
                name="BB下限", line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(255,255,255,0.05)",
            ), row=1, col=1)

        # 一目均衡表
        if st.session_state.show_ichimoku and "Ichimoku_Tenkan" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["Ichimoku_Tenkan"],
                name="転換線", line=dict(color="#FF9800", width=1),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["Ichimoku_Kijun"],
                name="基準線", line=dict(color="#2196F3", width=1),
            ), row=1, col=1)
            if "Ichimoku_SpanA" in hist_df.columns and "Ichimoku_SpanB" in hist_df.columns:
                fig.add_trace(go.Scatter(
                    x=hist_df.index, y=hist_df["Ichimoku_SpanA"],
                    name="先行スパンA", line=dict(color="rgba(76,175,80,0.5)", width=0),
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=hist_df.index, y=hist_df["Ichimoku_SpanB"],
                    name="先行スパンB", line=dict(color="rgba(244,67,54,0.5)", width=0),
                    fill="tonexty", fillcolor="rgba(76,175,80,0.1)",
                ), row=1, col=1)

        # サポート・レジスタンスライン
        sr_levels = detect_support_resistance(hist_df)
        for level in sr_levels.get("support", [])[:3]:
            fig.add_hline(y=level, line_dash="dash", line_color="green",
                          annotation_text=f"S: ¥{level:,.0f}", row=1, col=1, opacity=0.5)
        for level in sr_levels.get("resistance", [])[:3]:
            fig.add_hline(y=level, line_dash="dash", line_color="red",
                          annotation_text=f"R: ¥{level:,.0f}", row=1, col=1, opacity=0.5)

        # ゴールデンクロス / デッドクロス マーカー
        crosses = detect_golden_dead_cross(hist_df)
        for cross in crosses[-5:]:  # 直近5つ
            marker_color = "green" if cross["type"] == "golden_cross" else "red"
            marker_symbol = "triangle-up" if cross["type"] == "golden_cross" else "triangle-down"
            cross_price = hist_df.loc[cross["date"], "Close"] if cross["date"] in hist_df.index else None
            if cross_price:
                fig.add_trace(go.Scatter(
                    x=[cross["date"]], y=[cross_price],
                    mode="markers",
                    marker=dict(color=marker_color, size=12, symbol=marker_symbol),
                    name=cross["label"],
                    showlegend=False,
                ), row=1, col=1)

        # MACD
        if "MACD" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["MACD"],
                name="MACD", line=dict(color="#FF6B6B", width=1),
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["MACD_Signal"],
                name="シグナル", line=dict(color="#4488FF", width=1),
            ), row=2, col=1)
            colors = ["#FF4444" if v >= 0 else "#4488FF" for v in hist_df["MACD_Hist"].fillna(0)]
            fig.add_trace(go.Bar(
                x=hist_df.index, y=hist_df["MACD_Hist"],
                name="MACD Hist", marker_color=colors, opacity=0.5,
            ), row=2, col=1)

        # RSI
        if "RSI" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df.index, y=hist_df["RSI"],
                name="RSI", line=dict(color="#FFD700", width=1),
            ), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1, opacity=0.5)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1, opacity=0.5)

        # 出来高
        if st.session_state.show_volume:
            vol_colors = []
            for i in range(len(hist_df)):
                if i == 0:
                    vol_colors.append("#888888")
                elif hist_df["Close"].iloc[i] >= hist_df["Close"].iloc[i - 1]:
                    vol_colors.append("#FF4444")
                else:
                    vol_colors.append("#4488FF")
            fig.add_trace(go.Bar(
                x=hist_df.index, y=hist_df["Volume"],
                name="出来高", marker_color=vol_colors, opacity=0.6,
            ), row=n_rows, col=1)

        fig.update_layout(
            height=700,
            template="plotly_dark",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=20, t=30, b=20),
        )
        fig.update_xaxes(type="date")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("チャートデータが取得できませんでした。")

# --- 投資判断サマリー ---
with summary_col:
    st.markdown("### 🎯 投資判断")

    # テクニカルシグナル取得
    tech_signals = get_technical_signals(hist_df) if hist_df is not None and not hist_df.empty else []
    fund_evals = evaluate_fundamental(fundamental)
    sentiment_data = analyze_posts_sentiment(board_posts) if board_posts else None

    # ML予測
    if hist_df is not None and not hist_df.empty and not st.session_state.models_trained:
        with st.spinner("AIモデル学習中..."):
            st.session_state.price_predictor.train(hist_df)
            st.session_state.trend_classifier.train(hist_df)
            st.session_state.volatility_model.train(hist_df)
            st.session_state.models_trained = True

    trend_pred = st.session_state.trend_classifier.predict(hist_df) if hist_df is not None else None

    # リスク評価
    nikkei_df = fetch_nikkei225_data(st.session_state.chart_period)
    risk_data = get_risk_assessment(hist_df, nikkei_df) if hist_df is not None and not hist_df.empty else None

    # 総合スコア算出
    score_data = calculate_investment_score(
        tech_signals, fund_evals, sentiment_data, trend_pred, risk_data
    )

    total_score = score_data["total_score"]
    recommendation = score_data["recommendation"]
    confidence = score_data["confidence"]

    # スコアゲージ表示
    gauge_color = "#44FF44" if total_score > 0.1 else "#FF4444" if total_score < -0.1 else "#FFD700"
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=(total_score + 1) * 50,  # -1~1を0~100に変換
        number={"suffix": "", "font": {"size": 24}},
        title={"text": recommendation, "font": {"size": 20}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": gauge_color},
            "steps": [
                {"range": [0, 30], "color": "#3a1a1a"},
                {"range": [30, 45], "color": "#3a2a1a"},
                {"range": [45, 55], "color": "#2a2a1a"},
                {"range": [55, 70], "color": "#1a3a2a"},
                {"range": [70, 100], "color": "#1a3a1a"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": (total_score + 1) * 50,
            },
        },
    ))
    fig_gauge.update_layout(
        height=200, margin=dict(l=20, r=20, t=40, b=10),
        template="plotly_dark",
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown(f"**信頼度:** {confidence:.0%}")

    # 判断根拠
    st.markdown("**判断根拠:**")
    for reason in score_data["reasons"]:
        st.markdown(f"- {reason}")

    # エントリー・エグジット提案
    if realtime and realtime.get("price"):
        current_price = float(realtime["price"])
        entry_exit = suggest_entry_exit(
            current_price,
            sr_levels.get("support", []) if hist_df is not None else [],
            sr_levels.get("resistance", []) if hist_df is not None else [],
            recommendation,
        )
        st.markdown("---")
        st.markdown("**推奨ポイント:**")
        if entry_exit["entry_price"]:
            st.markdown(f"- エントリー: ¥{entry_exit['entry_price']:,.0f}")
        if entry_exit["stop_loss"]:
            st.markdown(f"- 損切り: ¥{entry_exit['stop_loss']:,.0f}")
        if entry_exit["take_profit"]:
            st.markdown(f"- 利確: ¥{entry_exit['take_profit']:,.0f}")

    # リスクレベル
    if risk_data:
        risk_score = risk_data.get("risk_score", 50)
        risk_level = risk_data.get("risk_level", "中程度")
        risk_color = "#FF4444" if risk_score > 60 else "#FFD700" if risk_score > 40 else "#44FF44"
        st.markdown("---")
        st.markdown(f"**リスクレベル:** :{risk_level}")
        st.progress(risk_score / 100)

st.markdown("---")

# === 下部パネル ===
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 テクニカル指標", "💰 ファンダメンタル", "💬 センチメント", "🤖 AI予測", "⚠️ リスク評価",
])

# --- テクニカル指標パネル ---
with tab1:
    st.markdown("### テクニカル指標シグナル")

    if tech_signals:
        sig_cols = st.columns(len(tech_signals))
        for i, sig in enumerate(tech_signals):
            with sig_cols[i]:
                signal = sig["signal"]
                if signal == "買い":
                    st.success(f"**{sig['name']}**\n\n{sig['value']}\n\n🟢 {signal}")
                elif signal == "売り":
                    st.error(f"**{sig['name']}**\n\n{sig['value']}\n\n🔴 {signal}")
                else:
                    st.warning(f"**{sig['name']}**\n\n{sig['value']}\n\n🟡 {signal}")
    else:
        st.info("テクニカル指標を計算できませんでした。")

    # ゴールデンクロス/デッドクロス
    if hist_df is not None and not hist_df.empty:
        crosses = detect_golden_dead_cross(hist_df)
        if crosses:
            st.markdown("#### クロスシグナル（直近）")
            for cross in crosses[-5:]:
                date_str = cross["date"].strftime("%Y-%m-%d") if hasattr(cross["date"], "strftime") else str(cross["date"])
                icon = "🟢" if cross["type"] == "golden_cross" else "🔴"
                st.markdown(f"{icon} **{date_str}** - {cross['label']} ({cross['signal']})")

# --- ファンダメンタルパネル ---
with tab2:
    st.markdown("### ファンダメンタル分析")

    if fund_evals:
        fund_cols = st.columns(min(4, len(fund_evals)))
        for i, ev in enumerate(fund_evals):
            with fund_cols[i % len(fund_cols)]:
                signal = ev["signal"]
                if signal == "買い":
                    st.success(f"**{ev['name']}**\n\n{ev['value']}\n\n{ev['evaluation']}")
                elif signal == "売り":
                    st.error(f"**{ev['name']}**\n\n{ev['value']}\n\n{ev['evaluation']}")
                elif signal == "注意":
                    st.warning(f"**{ev['name']}**\n\n{ev['value']}\n\n{ev['evaluation']}")
                else:
                    st.info(f"**{ev['name']}**\n\n{ev['value']}\n\n{ev['evaluation']}")

        # セクター情報
        if fundamental:
            st.markdown("---")
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.markdown(f"**セクター:** {fundamental.get('sector', '---')}")
                st.markdown(f"**業種:** {fundamental.get('industry', '---')}")
            with info_col2:
                beta = fundamental.get("beta")
                st.markdown(f"**ベータ値:** {beta:.2f}" if beta else "**ベータ値:** ---")
                st.markdown(f"**50日移動平均:** ¥{fundamental.get('fifty_day_average', 0):,.0f}"
                            if fundamental.get("fifty_day_average") else "**50日移動平均:** ---")
    else:
        st.info("ファンダメンタルデータを取得できませんでした。")

# --- センチメント分析パネル ---
with tab3:
    st.markdown("### 掲示板センチメント分析")

    if sentiment_data and sentiment_data.get("total_posts", 0) > 0:
        sent_col1, sent_col2 = st.columns([1, 1])

        with sent_col1:
            avg_score = sentiment_data["average_score"]
            label = sentiment_data["label"]

            # センチメントゲージ
            sent_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=(avg_score + 1) * 50,
                number={"suffix": "", "font": {"size": 20}},
                title={"text": f"センチメント: {label}", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#44FF44" if avg_score > 0 else "#FF4444"},
                    "steps": [
                        {"range": [0, 30], "color": "#3a1a1a"},
                        {"range": [30, 50], "color": "#3a2a1a"},
                        {"range": [50, 70], "color": "#2a3a1a"},
                        {"range": [70, 100], "color": "#1a3a1a"},
                    ],
                },
            ))
            sent_gauge.update_layout(
                height=200, margin=dict(l=20, r=20, t=40, b=10),
                template="plotly_dark",
            )
            st.plotly_chart(sent_gauge, use_container_width=True)

            # 分布
            dist = sentiment_data["sentiment_distribution"]
            st.markdown("**感情分布:**")
            total = sentiment_data["total_posts"]
            for label, count in dist.items():
                pct = (count / total * 100) if total > 0 else 0
                st.markdown(f"- {label}: {count}件 ({pct:.0f}%)")

        with sent_col2:
            # ワードクラウド
            keywords = sentiment_data.get("keywords", [])
            if keywords:
                st.markdown("**話題のキーワード Top 10:**")
                for i, (word, count) in enumerate(keywords[:10], 1):
                    bar_len = int(count / max(1, keywords[0][1]) * 20)
                    bar = "█" * bar_len
                    st.markdown(f"{i}. **{word}** ({count}) {bar}")

                # ワードクラウド画像生成
                try:
                    from wordcloud import WordCloud
                    import matplotlib.pyplot as plt

                    word_freq = dict(keywords)
                    if word_freq:
                        wc = WordCloud(
                            width=400, height=200,
                            background_color="#0E1117",
                            colormap="coolwarm",
                            font_path=None,  # システムフォントを使用
                            max_words=50,
                        ).generate_from_frequencies(word_freq)

                        fig_wc, ax = plt.subplots(figsize=(8, 4))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        fig_wc.patch.set_facecolor("#0E1117")
                        st.pyplot(fig_wc)
                        plt.close(fig_wc)
                except Exception:
                    pass  # ワードクラウド生成失敗は無視

        # コメントフィード
        st.markdown("---")
        st.markdown("#### 最新コメント")
        for post in board_posts[:10]:
            title = post.get("タイトル", "")
            body = post.get("本文", "")
            timestamp = post.get("日時", "")
            agrees = post.get("そう思う", "")
            disagrees = post.get("そう思わない", "")

            # 感情分析
            from src.analysis.sentiment import analyze_sentiment
            sent = analyze_sentiment(f"{title} {body}")
            sent_icon = "🟢" if sent["score"] > 0.2 else "🔴" if sent["score"] < -0.2 else "⚪"

            with st.expander(f"{sent_icon} {title[:50] if title else body[:50]}... ({timestamp})"):
                if body:
                    st.markdown(body[:300])
                if agrees or disagrees:
                    st.markdown(f"👍 {agrees} / 👎 {disagrees}")
    else:
        st.info("掲示板データがありません。")

# --- AI予測パネル ---
with tab4:
    st.markdown("### AI予測")

    if hist_df is not None and not hist_df.empty:
        pred_col1, pred_col2 = st.columns([2, 1])

        with pred_col1:
            # 価格予測グラフ
            price_pred = st.session_state.price_predictor.predict(hist_df, days=10)

            if price_pred:
                fig_pred = go.Figure()

                # 実績（直近30日）
                recent_df = hist_df.tail(30)
                fig_pred.add_trace(go.Scatter(
                    x=recent_df.index, y=recent_df["Close"],
                    name="実績", line=dict(color="#FFD700", width=2),
                ))

                # 予測
                pred_dates = price_pred["dates"]
                pred_prices = price_pred["predictions"]
                fig_pred.add_trace(go.Scatter(
                    x=pred_dates, y=pred_prices,
                    name="予測", line=dict(color="#FF6B6B", width=2, dash="dash"),
                ))

                # 信頼区間
                fig_pred.add_trace(go.Scatter(
                    x=pred_dates, y=price_pred["confidence_upper"],
                    name="95%上限", line=dict(color="rgba(255,107,107,0.3)", width=0),
                    showlegend=False,
                ))
                fig_pred.add_trace(go.Scatter(
                    x=pred_dates, y=price_pred["confidence_lower"],
                    name="95%下限", line=dict(color="rgba(255,107,107,0.3)", width=0),
                    fill="tonexty", fillcolor="rgba(255,107,107,0.1)",
                    showlegend=False,
                ))

                fig_pred.update_layout(
                    height=350, template="plotly_dark",
                    title="株価予測（10営業日先）",
                    xaxis_title="日付", yaxis_title="株価 (¥)",
                    margin=dict(l=50, r=20, t=40, b=30),
                )
                st.plotly_chart(fig_pred, use_container_width=True)
            else:
                st.info("価格予測モデルを学習できませんでした。データが不足している可能性があります。")

        with pred_col2:
            # トレンド予測
            if trend_pred:
                st.markdown("#### トレンド予測")
                trend = trend_pred["trend"]
                trend_conf = trend_pred["confidence"]

                if trend == "上昇":
                    st.success(f"📈 **{trend}** (信頼度: {trend_conf:.0%})")
                elif trend == "下降":
                    st.error(f"📉 **{trend}** (信頼度: {trend_conf:.0%})")
                else:
                    st.warning(f"➡️ **{trend}** (信頼度: {trend_conf:.0%})")

                # 確率分布
                st.markdown("**トレンド確率:**")
                probs = trend_pred.get("probabilities", {})
                for label, prob in probs.items():
                    st.progress(prob, text=f"{label}: {prob:.0%}")

                if trend_pred.get("model_accuracy"):
                    st.markdown(f"モデル精度: {trend_pred['model_accuracy']:.1%}")

            # ボラティリティ予測
            vol_pred = st.session_state.volatility_model.predict(days=5)
            if vol_pred:
                st.markdown("---")
                st.markdown("#### ボラティリティ予測")
                current_vol = vol_pred["current_annual_vol"]
                st.metric("年率ボラティリティ", f"{current_vol:.1%}")
    else:
        st.info("AI予測にはチャートデータが必要です。")

# --- リスク評価パネル ---
with tab5:
    st.markdown("### リスク評価")

    if risk_data:
        risk_col1, risk_col2 = st.columns(2)

        with risk_col1:
            # ボラティリティ推移
            vol_series = risk_data.get("volatility_series")
            if vol_series is not None and not vol_series.empty:
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(
                    x=vol_series.index, y=vol_series,
                    name="ボラティリティ（年率）",
                    line=dict(color="#FF6B6B"),
                    fill="tozeroy", fillcolor="rgba(255,107,107,0.1)",
                ))
                fig_vol.update_layout(
                    height=300, template="plotly_dark",
                    title="ヒストリカルボラティリティ推移",
                    margin=dict(l=50, r=20, t=40, b=30),
                )
                st.plotly_chart(fig_vol, use_container_width=True)

            # 最大ドローダウン
            dd = risk_data.get("max_drawdown", {})
            dd_series = dd.get("drawdown_series")
            if dd_series is not None and not dd_series.empty:
                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=dd_series.index, y=dd_series * 100,
                    name="ドローダウン(%)",
                    line=dict(color="#4488FF"),
                    fill="tozeroy", fillcolor="rgba(68,136,255,0.1)",
                ))
                fig_dd.update_layout(
                    height=250, template="plotly_dark",
                    title="ドローダウン推移",
                    margin=dict(l=50, r=20, t=40, b=30),
                )
                st.plotly_chart(fig_dd, use_container_width=True)

        with risk_col2:
            # リスク指標
            st.markdown("#### リスク指標")

            vol_val = risk_data.get("volatility")
            st.metric("年率ボラティリティ", f"{vol_val:.1%}" if vol_val else "---")

            dd_val = dd.get("max_drawdown_pct")
            st.metric("最大ドローダウン", f"{dd_val:.1f}%" if dd_val else "---")

            var_data = risk_data.get("var")
            if var_data:
                st.metric(
                    f"VaR ({var_data['confidence']:.0%}, {var_data['horizon']}日)",
                    f"{var_data['historical_var_adj']:.2%}",
                )
                st.metric(
                    "VaR金額 (100株)",
                    f"¥{var_data['var_amount_100shares']:,.0f}",
                )

            beta = risk_data.get("beta")
            st.metric("ベータ値（対日経225）", f"{beta:.2f}" if beta else "---")

            sharpe = risk_data.get("sharpe_ratio")
            st.metric("シャープレシオ", f"{sharpe:.2f}" if sharpe else "---")

            st.markdown("---")
            risk_score = risk_data.get("risk_score", 50)
            risk_level = risk_data.get("risk_level", "中程度")
            st.markdown(f"**総合リスクスコア: {risk_score:.0f}/100 ({risk_level})**")
            st.progress(risk_score / 100)
    else:
        st.info("リスク評価にはチャートデータが必要です。")

# --- アラート表示 ---
alert_mgr = st.session_state.alert_manager
recent_alerts = alert_mgr.get_recent_alerts(5)
if recent_alerts:
    st.markdown("---")
    st.markdown("### 🔔 アラート履歴")
    for alert in recent_alerts:
        icon = "⚠️" if alert.alert_type in ("price_upper", "price_lower") else "📊"
        st.markdown(f"{icon} **{alert.timestamp.strftime('%H:%M:%S')}** - {alert.message}")

# --- フッター ---
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#666; font-size:0.8rem;'>"
    "⚠️ 本アプリの情報は投資助言を構成するものではありません。"
    "投資判断は必ずご自身の責任で行ってください。"
    "予測や分析結果は参考情報であり、将来の結果を保証するものではありません。"
    "</div>",
    unsafe_allow_html=True,
)

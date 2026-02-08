"""銘柄比較ページ"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plotly.graph_objects as go
import streamlit as st

from src.data.fetcher import fetch_historical_data, fetch_fundamental_data, fetch_realtime_price
from src.data.preprocessor import clean_price_data

st.set_page_config(page_title="銘柄比較", page_icon="📊", layout="wide")

st.markdown("## 📊 銘柄比較")

# 銘柄入力
col1, col2, col3 = st.columns(3)
with col1:
    code1 = st.text_input("銘柄1", value="7203", placeholder="銘柄コード")
with col2:
    code2 = st.text_input("銘柄2", value="6758", placeholder="銘柄コード")
with col3:
    code3 = st.text_input("銘柄3", value="9984", placeholder="銘柄コード（任意）")

codes = [c.strip() for c in [code1, code2, code3] if c.strip()]

if not codes:
    st.info("比較する銘柄コードを入力してください。")
    st.stop()

period = st.selectbox("比較期間", ["3mo", "6mo", "1y", "2y"], index=2)

# データ取得
with st.spinner("データ取得中..."):
    data = {}
    for code in codes:
        df = fetch_historical_data(code, period=period)
        if df is not None and not df.empty:
            df = clean_price_data(df)
            data[code] = df

if not data:
    st.error("データを取得できませんでした。")
    st.stop()

# --- 株価比較チャート（正規化）---
st.markdown("### 株価推移比較（起点=100）")
fig_norm = go.Figure()
colors = ["#FF6B6B", "#4488FF", "#44FF44", "#FFD700", "#FF44FF"]

for i, (code, df) in enumerate(data.items()):
    normalized = df["Close"] / df["Close"].iloc[0] * 100
    fig_norm.add_trace(go.Scatter(
        x=df.index, y=normalized,
        name=code, line=dict(color=colors[i % len(colors)], width=2),
    ))

fig_norm.update_layout(
    height=400, template="plotly_dark",
    yaxis_title="正規化株価 (起点=100)",
    margin=dict(l=50, r=20, t=20, b=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig_norm, use_container_width=True)

# --- ファンダメンタル比較 ---
st.markdown("### ファンダメンタル指標比較")

fund_data = {}
for code in codes:
    f = fetch_fundamental_data(code)
    if f:
        fund_data[code] = f

if fund_data:
    metrics = ["per", "pbr", "roe", "roa", "dividend_yield", "profit_margin"]
    metric_labels = {
        "per": "PER", "pbr": "PBR", "roe": "ROE", "roa": "ROA",
        "dividend_yield": "配当利回り", "profit_margin": "純利益率",
    }

    compare_cols = st.columns(len(fund_data))
    for i, (code, f) in enumerate(fund_data.items()):
        with compare_cols[i]:
            rt = fetch_realtime_price(code)
            name = rt.get("name", code) if rt else code
            st.markdown(f"**{name} ({code})**")
            for m in metrics:
                val = f.get(m)
                if val is not None:
                    if m in ("roe", "roa", "dividend_yield", "profit_margin"):
                        st.metric(metric_labels[m], f"{val * 100:.2f}%")
                    else:
                        st.metric(metric_labels[m], f"{val:.2f}")
                else:
                    st.metric(metric_labels[m], "---")

# --- 出来高比較 ---
st.markdown("### 出来高比較")
fig_vol = go.Figure()
for i, (code, df) in enumerate(data.items()):
    fig_vol.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        name=code, marker_color=colors[i % len(colors)],
        opacity=0.6,
    ))

fig_vol.update_layout(
    height=300, template="plotly_dark",
    barmode="overlay",
    margin=dict(l=50, r=20, t=20, b=30),
)
st.plotly_chart(fig_vol, use_container_width=True)

st.markdown(
    "<div style='text-align:center; color:#666; font-size:0.8rem;'>"
    "⚠️ 本アプリの情報は投資助言ではありません。投資判断は自己責任でお願いします。"
    "</div>",
    unsafe_allow_html=True,
)

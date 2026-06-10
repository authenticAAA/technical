"""Streamlit 版 米国株テクニカル分析アプリ。

FastAPI 版と同じ計算ロジック (app.indicators / app.signals / app.data) を再利用し、
コマンド操作なしでクラウド (Streamlit Community Cloud 等) に公開できる。

ローカル起動: streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app import data as data_mod
from app import indicators, signals

st.set_page_config(page_title="米国株テクニカル分析", page_icon="📈", layout="wide")

st.title("📈 米国株テクニカル分析")

# ---- 入力 ----
with st.sidebar:
    st.header("設定")
    ticker = st.text_input("ティッカー", value="AAPL").strip().upper()
    period = st.selectbox(
        "期間", ["3mo", "6mo", "1y", "2y", "5y"], index=2,
    )
    interval = st.selectbox(
        "足", ["1d", "1wk", "1h"], index=0,
        format_func=lambda x: {"1d": "日足", "1wk": "週足", "1h": "1時間足"}[x],
    )
    run = st.button("分析", type="primary", use_container_width=True)

st.caption("データ提供: Yahoo Finance ／ 本ツールは教育目的であり投資助言ではありません。")


@st.cache_data(ttl=60, show_spinner=False)
def load(ticker: str, period: str, interval: str):
    """データ取得 + 指標計算 + シグナル判定をまとめて行いキャッシュする。"""
    df = data_mod.fetch_history(ticker, period=period, interval=interval)
    enriched = indicators.compute_all(df)
    sig = signals.generate(enriched)
    name = data_mod.get_company_name(ticker)
    return enriched, sig, name


def build_chart(df: pd.DataFrame) -> go.Figure:
    """価格 / RSI / MACD の 3 段チャートを生成する。"""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03,
        subplot_titles=("価格 / 移動平均 / ボリンジャー", "RSI (14)", "MACD"),
    )
    x = df.index

    # 価格 (ローソク足)
    fig.add_trace(go.Candlestick(
        x=x, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="価格", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)
    for col, color in [("sma_20", "#f1c40f"), ("sma_50", "#58a6ff"), ("sma_200", "#e056fd")]:
        fig.add_trace(go.Scatter(x=x, y=df[col], name=col.upper(), line=dict(color=color, width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["bb_upper"], name="BB上", line=dict(color="rgba(139,148,158,0.5)", width=1, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["bb_lower"], name="BB下", line=dict(color="rgba(139,148,158,0.5)", width=1, dash="dot"), fill="tonexty", fillcolor="rgba(139,148,158,0.07)"), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=x, y=df["rsi_14"], name="RSI", line=dict(color="#58a6ff", width=1)), row=2, col=1)
    fig.add_hline(y=70, line=dict(color="#ef5350", width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color="#26a69a", width=1, dash="dash"), row=2, col=1)

    # MACD
    hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["hist"].fillna(0)]
    fig.add_trace(go.Bar(x=x, y=df["hist"], name="ヒスト", marker_color=hist_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["macd"], name="MACD", line=dict(color="#58a6ff", width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["signal"], name="シグナル", line=dict(color="#f1c40f", width=1)), row=3, col=1)

    fig.update_layout(
        template="plotly_dark", height=760, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.04),
        hovermode="x unified",
    )
    return fig


if run or ticker:
    if not ticker:
        st.info("ティッカーを入力してください。")
        st.stop()
    try:
        with st.spinner(f"{ticker} を取得中..."):
            df, sig, name = load(ticker, period, interval)
    except data_mod.FetchError as exc:
        st.error(f"取得に失敗しました: {exc}")
        st.stop()

    st.subheader(f"{name + ' ' if name else ''}({ticker})")

    # ---- サマリー ----
    last = df.iloc[-1]
    verdict_color = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪"}[sig["verdict"]]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("総合判定", f"{verdict_color} {sig['verdict']}", f"スコア {sig['score']}")
    c2.metric("終値", f"${last['Close']:.2f}")
    c3.metric("RSI(14)", f"{last['rsi_14']:.1f}" if pd.notna(last["rsi_14"]) else "—")
    c4.metric("SMA200", f"${last['sma_200']:.2f}" if pd.notna(last["sma_200"]) else "—")
    c5.metric("ATR(14)", f"{last['atr_14']:.2f}" if pd.notna(last["atr_14"]) else "—")

    # ---- シグナルチップ ----
    if sig["signals"]:
        cols = st.columns(min(len(sig["signals"]), 4))
        for i, s in enumerate(sig["signals"]):
            icon = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}[s["type"]]
            cols[i % len(cols)].info(f"{icon} **{s['name']}**\n\n{s['detail']}")

    # ---- チャート ----
    st.plotly_chart(build_chart(df), use_container_width=True)

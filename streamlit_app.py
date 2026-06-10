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
from app import indicators, patterns, signals

st.set_page_config(page_title="米国株テクニカル分析", page_icon="📈", layout="wide")

st.title("📈 米国株テクニカル分析")

# 価格チャートへ重ねる指標 / 別ペインで描く指標の定義
OVERLAYS = ["移動平均", "ボリンジャー", "一目均衡表", "パラボリックSAR", "サポート/レジスタンス", "ピボット"]
PANES = ["RSI", "MACD", "ストキャス", "ADX", "CCI", "Williams %R", "MFI", "OBV", "ROC"]

# ---- 入力 ----
with st.sidebar:
    st.header("設定")
    ticker = st.text_input("ティッカー", value="AAPL").strip().upper()
    period = st.selectbox("期間", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    interval = st.selectbox(
        "足", ["1d", "1wk", "1h"], index=0,
        format_func=lambda x: {"1d": "日足", "1wk": "週足", "1h": "1時間足"}[x],
    )
    run = st.button("分析", type="primary", width="stretch")

    st.divider()
    st.subheader("価格チャートに重ねる指標")
    overlays = st.multiselect(
        "ドロップダウンから選択", OVERLAYS,
        default=["移動平均", "ボリンジャー", "サポート/レジスタンス"],
    )

    st.subheader("別パネルで表示する指標")
    panes = st.multiselect(
        "ドロップダウンから選択 ", PANES, default=["RSI", "MACD"],
    )

st.caption("データ提供: Yahoo Finance ／ 本ツールは教育目的であり投資助言ではありません。")


@st.cache_data(ttl=60, show_spinner=False)
def load(ticker: str, period: str, interval: str):
    """データ取得 + 指標計算 + シグナル + フォーメーションをまとめて行いキャッシュする。"""
    df = data_mod.fetch_history(ticker, period=period, interval=interval)
    enriched = indicators.compute_all(df)
    sig = signals.generate(enriched)
    form = patterns.detect(enriched)
    name = data_mod.get_company_name(ticker)
    return enriched, sig, form, name


def _add_pane(fig, row, name, df):
    """指定パネル名に応じてサブプロットへトレースを追加する。"""
    x = df.index
    if name == "RSI":
        fig.add_trace(go.Scatter(x=x, y=df["rsi_14"], name="RSI", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_hline(y=70, line=dict(color="#ef5350", width=1, dash="dash"), row=row, col=1)
        fig.add_hline(y=30, line=dict(color="#26a69a", width=1, dash="dash"), row=row, col=1)
    elif name == "MACD":
        colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["hist"].fillna(0)]
        fig.add_trace(go.Bar(x=x, y=df["hist"], name="ヒスト", marker_color=colors), row=row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["macd"], name="MACD", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["signal"], name="シグナル", line=dict(color="#f1c40f", width=1)), row=row, col=1)
    elif name == "ストキャス":
        fig.add_trace(go.Scatter(x=x, y=df["stoch_k"], name="%K", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["stoch_d"], name="%D", line=dict(color="#f1c40f", width=1)), row=row, col=1)
        fig.add_hline(y=80, line=dict(color="#ef5350", width=1, dash="dash"), row=row, col=1)
        fig.add_hline(y=20, line=dict(color="#26a69a", width=1, dash="dash"), row=row, col=1)
    elif name == "ADX":
        fig.add_trace(go.Scatter(x=x, y=df["adx"], name="ADX", line=dict(color="#e6edf3", width=1.5)), row=row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["plus_di"], name="+DI", line=dict(color="#26a69a", width=1)), row=row, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["minus_di"], name="-DI", line=dict(color="#ef5350", width=1)), row=row, col=1)
        fig.add_hline(y=25, line=dict(color="#8b949e", width=1, dash="dash"), row=row, col=1)
    elif name == "CCI":
        fig.add_trace(go.Scatter(x=x, y=df["cci_20"], name="CCI", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_hline(y=100, line=dict(color="#ef5350", width=1, dash="dash"), row=row, col=1)
        fig.add_hline(y=-100, line=dict(color="#26a69a", width=1, dash="dash"), row=row, col=1)
    elif name == "Williams %R":
        fig.add_trace(go.Scatter(x=x, y=df["williams_r"], name="%R", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_hline(y=-20, line=dict(color="#ef5350", width=1, dash="dash"), row=row, col=1)
        fig.add_hline(y=-80, line=dict(color="#26a69a", width=1, dash="dash"), row=row, col=1)
    elif name == "MFI":
        fig.add_trace(go.Scatter(x=x, y=df["mfi_14"], name="MFI", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_hline(y=80, line=dict(color="#ef5350", width=1, dash="dash"), row=row, col=1)
        fig.add_hline(y=20, line=dict(color="#26a69a", width=1, dash="dash"), row=row, col=1)
    elif name == "OBV":
        fig.add_trace(go.Scatter(x=x, y=df["obv"], name="OBV", line=dict(color="#e056fd", width=1)), row=row, col=1)
    elif name == "ROC":
        fig.add_trace(go.Scatter(x=x, y=df["roc_12"], name="ROC", line=dict(color="#58a6ff", width=1)), row=row, col=1)
        fig.add_hline(y=0, line=dict(color="#8b949e", width=1, dash="dash"), row=row, col=1)


def build_chart(df: pd.DataFrame, overlays: list[str], panes: list[str], form: dict) -> go.Figure:
    """価格 + 選択された指標パネルを縦に並べたチャートを生成する。"""
    n_rows = 1 + len(panes)
    price_h = 0.6 if panes else 1.0
    rest = (1.0 - price_h) / len(panes) if panes else 0
    row_heights = [price_h] + [rest] * len(panes)

    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        row_heights=row_heights, vertical_spacing=0.03,
        subplot_titles=["価格"] + panes,
    )
    x = df.index

    # 価格 (ローソク足)
    fig.add_trace(go.Candlestick(
        x=x, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="価格", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    if "移動平均" in overlays:
        for col, color in [("sma_20", "#f1c40f"), ("sma_50", "#58a6ff"), ("sma_200", "#e056fd")]:
            fig.add_trace(go.Scatter(x=x, y=df[col], name=col.upper(), line=dict(color=color, width=1)), row=1, col=1)
    if "ボリンジャー" in overlays:
        fig.add_trace(go.Scatter(x=x, y=df["bb_upper"], name="BB上", line=dict(color="rgba(139,148,158,0.5)", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["bb_lower"], name="BB下", line=dict(color="rgba(139,148,158,0.5)", width=1, dash="dot"), fill="tonexty", fillcolor="rgba(139,148,158,0.07)"), row=1, col=1)
    if "一目均衡表" in overlays:
        fig.add_trace(go.Scatter(x=x, y=df["ichi_tenkan"], name="転換線", line=dict(color="#00bcd4", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["ichi_kijun"], name="基準線", line=dict(color="#ff9800", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["ichi_senkou_a"], name="先行A", line=dict(color="rgba(38,166,154,0.4)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["ichi_senkou_b"], name="先行B(雲)", line=dict(color="rgba(239,83,80,0.4)", width=1), fill="tonexty", fillcolor="rgba(120,120,160,0.12)"), row=1, col=1)
    if "パラボリックSAR" in overlays:
        fig.add_trace(go.Scatter(x=x, y=df["psar"], name="SAR", mode="markers", marker=dict(color="#ffeb3b", size=3)), row=1, col=1)
    if "サポート/レジスタンス" in overlays:
        for r in form.get("resistance", [])[:3]:
            fig.add_hline(y=r["level"], line=dict(color="rgba(239,83,80,0.5)", width=1, dash="dash"),
                          annotation_text=f"R {r['level']:.1f}", annotation_position="right", row=1, col=1)
        for s in form.get("support", [])[:3]:
            fig.add_hline(y=s["level"], line=dict(color="rgba(38,166,154,0.5)", width=1, dash="dash"),
                          annotation_text=f"S {s['level']:.1f}", annotation_position="right", row=1, col=1)
    if "ピボット" in overlays:
        ph = form.get("pivot_highs", [])
        pl = form.get("pivot_lows", [])
        if ph:
            fig.add_trace(go.Scatter(x=[p["time"] for p in ph], y=[p["price"] for p in ph],
                          name="高値ピボット", mode="markers", marker=dict(color="#ef5350", size=7, symbol="triangle-down")), row=1, col=1)
        if pl:
            fig.add_trace(go.Scatter(x=[p["time"] for p in pl], y=[p["price"] for p in pl],
                          name="安値ピボット", mode="markers", marker=dict(color="#26a69a", size=7, symbol="triangle-up")), row=1, col=1)

    for i, pane in enumerate(panes, start=2):
        _add_pane(fig, i, pane, df)

    fig.update_layout(
        template="plotly_dark", height=420 + 170 * len(panes),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.02),
        hovermode="x unified",
    )
    return fig


if run or ticker:
    if not ticker:
        st.info("ティッカーを入力してください。")
        st.stop()
    try:
        with st.spinner(f"{ticker} を取得中..."):
            df, sig, form, name = load(ticker, period, interval)
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
    c4.metric("ADX", f"{last['adx']:.0f}" if pd.notna(last["adx"]) else "—")
    c5.metric("ATR(14)", f"{last['atr_14']:.2f}" if pd.notna(last["atr_14"]) else "—")

    # ---- 指標シグナル ----
    if sig["signals"]:
        st.markdown("##### 📊 指標シグナル")
        cols = st.columns(min(len(sig["signals"]), 4))
        for i, s in enumerate(sig["signals"]):
            icon = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}[s["type"]]
            cols[i % len(cols)].info(f"{icon} **{s['name']}**\n\n{s['detail']}")

    # ---- フォーメーション分析 ----
    st.markdown("##### 🔺 フォーメーション分析")
    if form["patterns"]:
        cols = st.columns(min(len(form["patterns"]), 4))
        for i, p in enumerate(form["patterns"]):
            icon = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}[p["type"]]
            box = cols[i % len(cols)]
            text = f"{icon} **{p['name']}**\n\n{p['detail']}"
            if p["type"] == "bullish":
                box.success(text)
            elif p["type"] == "bearish":
                box.error(text)
            else:
                box.warning(text)
    else:
        st.caption("明確なフォーメーションは検出されませんでした。")

    res_txt = " / ".join(f"{r['level']:.2f}" for r in form["resistance"][:3]) or "—"
    sup_txt = " / ".join(f"{s['level']:.2f}" for s in form["support"][:3]) or "—"
    st.caption(f"🔴 レジスタンス: {res_txt}　🟢 サポート: {sup_txt}")

    # ---- チャート ----
    st.plotly_chart(build_chart(df, overlays, panes, form), width="stretch")

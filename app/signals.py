"""指標値からの売買シグナル判定。

compute_all() で算出済みの指標列を持つデータフレームを受け取り、
最新時点のシグナルとスコアを返す。
"""

from __future__ import annotations

import pandas as pd


def _cross_up(fast: pd.Series, slow: pd.Series) -> bool:
    """fast が slow を直近のバーで下から上に抜けたか。"""
    if len(fast) < 2:
        return False
    return (
        fast.iloc[-2] <= slow.iloc[-2]
        and fast.iloc[-1] > slow.iloc[-1]
        and pd.notna(fast.iloc[-2])
        and pd.notna(slow.iloc[-2])
    )


def _cross_down(fast: pd.Series, slow: pd.Series) -> bool:
    if len(fast) < 2:
        return False
    return (
        fast.iloc[-2] >= slow.iloc[-2]
        and fast.iloc[-1] < slow.iloc[-1]
        and pd.notna(fast.iloc[-2])
        and pd.notna(slow.iloc[-2])
    )


def generate(df: pd.DataFrame) -> dict:
    """最新バー時点のシグナル一覧と総合判定を返す。

    返り値:
      {
        "signals": [{"name","type","detail"}, ...],
        "score": int,            # 正=強気, 負=弱気
        "verdict": "BUY"|"SELL"|"NEUTRAL"
      }
    """
    signals: list[dict] = []
    score = 0

    def add(name: str, sig_type: str, detail: str, weight: int) -> None:
        nonlocal score
        signals.append({"name": name, "type": sig_type, "detail": detail})
        if sig_type == "bullish":
            score += weight
        elif sig_type == "bearish":
            score -= weight

    last = df.iloc[-1]

    # --- 移動平均のゴールデン/デッドクロス (50 vs 200) ---
    if "sma_50" in df and "sma_200" in df:
        if _cross_up(df["sma_50"], df["sma_200"]):
            add("ゴールデンクロス", "bullish", "SMA50 が SMA200 を上抜け", 3)
        elif _cross_down(df["sma_50"], df["sma_200"]):
            add("デッドクロス", "bearish", "SMA50 が SMA200 を下抜け", 3)

    # --- 価格と SMA200 の位置関係 (長期トレンド) ---
    if pd.notna(last.get("sma_200")):
        if last["Close"] > last["sma_200"]:
            add("長期トレンド", "bullish", "終値 > SMA200", 1)
        else:
            add("長期トレンド", "bearish", "終値 < SMA200", 1)

    # --- RSI ---
    rsi_val = last.get("rsi_14")
    if pd.notna(rsi_val):
        if rsi_val >= 70:
            add("RSI", "bearish", f"買われすぎ (RSI={rsi_val:.1f})", 2)
        elif rsi_val <= 30:
            add("RSI", "bullish", f"売られすぎ (RSI={rsi_val:.1f})", 2)
        else:
            add("RSI", "neutral", f"中立 (RSI={rsi_val:.1f})", 0)

    # --- MACD クロス ---
    if "macd" in df and "signal" in df:
        if _cross_up(df["macd"], df["signal"]):
            add("MACD", "bullish", "MACD がシグナルを上抜け", 2)
        elif _cross_down(df["macd"], df["signal"]):
            add("MACD", "bearish", "MACD がシグナルを下抜け", 2)
        elif pd.notna(last.get("hist")):
            if last["hist"] > 0:
                add("MACD", "bullish", "ヒストグラムがプラス", 1)
            else:
                add("MACD", "bearish", "ヒストグラムがマイナス", 1)

    # --- ボリンジャーバンド ---
    if pd.notna(last.get("bb_upper")) and pd.notna(last.get("bb_lower")):
        if last["Close"] >= last["bb_upper"]:
            add("ボリンジャー", "bearish", "上限バンドにタッチ", 1)
        elif last["Close"] <= last["bb_lower"]:
            add("ボリンジャー", "bullish", "下限バンドにタッチ", 1)

    # --- ストキャスティクス ---
    k = last.get("stoch_k")
    if pd.notna(k):
        if k >= 80:
            add("ストキャス", "bearish", f"買われすぎ (%K={k:.1f})", 1)
        elif k <= 20:
            add("ストキャス", "bullish", f"売られすぎ (%K={k:.1f})", 1)

    if score >= 3:
        verdict = "BUY"
    elif score <= -3:
        verdict = "SELL"
    else:
        verdict = "NEUTRAL"

    return {"signals": signals, "score": score, "verdict": verdict}

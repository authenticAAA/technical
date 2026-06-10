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

    # --- ADX (トレンドの強さ + 方向) ---
    adx_val = last.get("adx")
    pdi = last.get("plus_di")
    mdi = last.get("minus_di")
    if pd.notna(adx_val) and pd.notna(pdi) and pd.notna(mdi):
        if adx_val >= 25:
            if pdi > mdi:
                add("ADX", "bullish", f"強い上昇トレンド (ADX={adx_val:.0f})", 2)
            else:
                add("ADX", "bearish", f"強い下降トレンド (ADX={adx_val:.0f})", 2)
        else:
            add("ADX", "neutral", f"トレンド弱い (ADX={adx_val:.0f})", 0)

    # --- CCI ---
    cci_val = last.get("cci_20")
    if pd.notna(cci_val):
        if cci_val >= 100:
            add("CCI", "bearish", f"買われすぎ (CCI={cci_val:.0f})", 1)
        elif cci_val <= -100:
            add("CCI", "bullish", f"売られすぎ (CCI={cci_val:.0f})", 1)

    # --- Williams %R ---
    wr = last.get("williams_r")
    if pd.notna(wr):
        if wr >= -20:
            add("Williams%R", "bearish", f"買われすぎ (%R={wr:.0f})", 1)
        elif wr <= -80:
            add("Williams%R", "bullish", f"売られすぎ (%R={wr:.0f})", 1)

    # --- MFI (出来高加味) ---
    mfi_val = last.get("mfi_14")
    if pd.notna(mfi_val):
        if mfi_val >= 80:
            add("MFI", "bearish", f"資金流入過熱 (MFI={mfi_val:.0f})", 1)
        elif mfi_val <= 20:
            add("MFI", "bullish", f"資金流出過多 (MFI={mfi_val:.0f})", 1)

    # --- パラボリック SAR ---
    psar = last.get("psar")
    if pd.notna(psar):
        if last["Close"] > psar:
            add("SAR", "bullish", "価格が SAR の上 (上昇局面)", 1)
        else:
            add("SAR", "bearish", "価格が SAR の下 (下降局面)", 1)

    # --- 一目均衡表 (雲との位置関係) ---
    sa = last.get("ichi_senkou_a")
    sb = last.get("ichi_senkou_b")
    if pd.notna(sa) and pd.notna(sb):
        cloud_top = max(sa, sb)
        cloud_bottom = min(sa, sb)
        if last["Close"] > cloud_top:
            add("一目均衡表", "bullish", "価格が雲の上", 2)
        elif last["Close"] < cloud_bottom:
            add("一目均衡表", "bearish", "価格が雲の下", 2)
        else:
            add("一目均衡表", "neutral", "価格が雲の中 (方向感なし)", 0)

    if score >= 4:
        verdict = "BUY"
    elif score <= -4:
        verdict = "SELL"
    else:
        verdict = "NEUTRAL"

    return {"signals": signals, "score": score, "verdict": verdict}

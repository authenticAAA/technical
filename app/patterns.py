"""チャートフォーメーション（パターン）分析。

スイングの高値・安値（ピボット）を検出し、そこから以下を判定する:
  - サポート / レジスタンスライン
  - トレンド構造（高値・安値の切り上げ / 切り下げ）
  - ダブルトップ / ダブルボトム
  - ヘッドアンドショルダー / 逆ヘッドアンドショルダー
  - 直近レンジのブレイクアウト / ブレイクダウン

すべて pandas / numpy のみで実装し、ネットワーク不要でテストできる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def find_pivots(
    series: pd.Series, left: int = 3, right: int = 3, kind: str = "high"
) -> list[int]:
    """スイングのピボット（局所的な高値/安値）の位置インデックスを返す。

    位置 i が左右 left/right 本の中で最大(高値) または最小(安値) のとき採用する。
    """
    arr = series.to_numpy(dtype=float)
    n = len(arr)
    out: list[int] = []
    for i in range(left, n - right):
        window = arr[i - left : i + right + 1]
        center = arr[i]
        if np.isnan(center):
            continue
        if kind == "high" and center == np.nanmax(window):
            out.append(i)
        elif kind == "low" and center == np.nanmin(window):
            out.append(i)
    # 連続するプラトー（同値の隣接ピボット）を間引く
    deduped: list[int] = []
    for i in out:
        if deduped and i - deduped[-1] <= right:
            # より極値に近い方を残す
            prev = deduped[-1]
            if kind == "high":
                if arr[i] >= arr[prev]:
                    deduped[-1] = i
            else:
                if arr[i] <= arr[prev]:
                    deduped[-1] = i
        else:
            deduped.append(i)
    return deduped


def _cluster_levels(prices: list[float], tol: float) -> list[dict]:
    """近接する価格をクラスタにまとめ、代表値とタッチ回数を返す。"""
    if not prices:
        return []
    prices = sorted(prices)
    clusters: list[list[float]] = [[prices[0]]]
    for p in prices[1:]:
        if abs(p - clusters[-1][-1]) / clusters[-1][-1] <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [
        {"level": float(np.mean(c)), "touches": len(c)} for c in clusters
    ]


def detect(df: pd.DataFrame, tol: float = 0.025) -> dict:
    """フォーメーション分析を行う。

    返り値:
      {
        "patterns": [{"name","type","detail"}, ...],
        "support": [{"level","touches"}, ...],
        "resistance": [{"level","touches"}, ...],
        "pivot_highs": [{"time","price"}, ...],
        "pivot_lows":  [{"time","price"}, ...],
      }
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    idx = df.index

    patterns: list[dict] = []

    def add(name: str, ptype: str, detail: str) -> None:
        patterns.append({"name": name, "type": ptype, "detail": detail})

    hi_piv = find_pivots(high, kind="high")
    lo_piv = find_pivots(low, kind="low")

    pivot_highs = [{"time": idx[i], "price": float(high.iloc[i])} for i in hi_piv]
    pivot_lows = [{"time": idx[i], "price": float(low.iloc[i])} for i in lo_piv]

    last_price = float(close.iloc[-1])

    # --- サポート / レジスタンス ---
    res_levels = _cluster_levels([p["price"] for p in pivot_highs], tol)
    sup_levels = _cluster_levels([p["price"] for p in pivot_lows], tol)
    # 現在価格より上=レジスタンス、下=サポート に整理
    resistance = sorted(
        [r for r in res_levels if r["level"] >= last_price],
        key=lambda r: r["level"],
    )
    support = sorted(
        [s for s in sup_levels if s["level"] <= last_price],
        key=lambda s: s["level"], reverse=True,
    )

    # --- トレンド構造（直近2つのスイング比較）---
    if len(hi_piv) >= 2 and len(lo_piv) >= 2:
        hh = high.iloc[hi_piv[-1]] > high.iloc[hi_piv[-2]]
        hl = low.iloc[lo_piv[-1]] > low.iloc[lo_piv[-2]]
        lh = high.iloc[hi_piv[-1]] < high.iloc[hi_piv[-2]]
        ll = low.iloc[lo_piv[-1]] < low.iloc[lo_piv[-2]]
        if hh and hl:
            add("上昇トレンド", "bullish", "高値・安値ともに切り上げ (HH/HL)")
        elif lh and ll:
            add("下降トレンド", "bearish", "高値・安値ともに切り下げ (LH/LL)")
        else:
            add("レンジ/転換", "neutral", "高値・安値の方向が不一致")

    # --- ダブルトップ / ダブルボトム ---
    if len(hi_piv) >= 2:
        p1, p2 = high.iloc[hi_piv[-2]], high.iloc[hi_piv[-1]]
        if abs(p1 - p2) / max(p1, p2) <= tol:
            # 2 つの山の間の谷（ネックライン）
            between = [j for j in lo_piv if hi_piv[-2] < j < hi_piv[-1]]
            neck = low.iloc[between[-1]] if between else None
            detail = "2つの高値がほぼ同水準"
            if neck is not None and last_price < neck:
                add("ダブルトップ", "bearish", f"{detail}・ネックライン割れ")
            else:
                add("ダブルトップ", "bearish", f"{detail}（上値抵抗の可能性）")
    if len(lo_piv) >= 2:
        b1, b2 = low.iloc[lo_piv[-2]], low.iloc[lo_piv[-1]]
        if abs(b1 - b2) / max(b1, b2) <= tol:
            between = [j for j in hi_piv if lo_piv[-2] < j < lo_piv[-1]]
            neck = high.iloc[between[-1]] if between else None
            detail = "2つの安値がほぼ同水準"
            if neck is not None and last_price > neck:
                add("ダブルボトム", "bullish", f"{detail}・ネックライン突破")
            else:
                add("ダブルボトム", "bullish", f"{detail}（下値支持の可能性）")

    # --- ヘッドアンドショルダー（直近3山 / 3谷）---
    if len(hi_piv) >= 3:
        a, b, c = (high.iloc[hi_piv[-3]], high.iloc[hi_piv[-2]], high.iloc[hi_piv[-1]])
        if b > a and b > c and abs(a - c) / max(a, c) <= tol * 2:
            add("ヘッドアンドショルダー", "bearish", "中央の山が最も高い天井型 (反転下落の目安)")
    if len(lo_piv) >= 3:
        a, b, c = (low.iloc[lo_piv[-3]], low.iloc[lo_piv[-2]], low.iloc[lo_piv[-1]])
        if b < a and b < c and abs(a - c) / max(a, c) <= tol * 2:
            add("逆ヘッドアンドショルダー", "bullish", "中央の谷が最も低い底型 (反転上昇の目安)")

    # --- ブレイクアウト / ブレイクダウン（直近20本のレンジ）---
    lookback = min(20, len(df) - 1)
    if lookback > 1:
        recent_high = high.iloc[-lookback - 1 : -1].max()
        recent_low = low.iloc[-lookback - 1 : -1].min()
        if last_price > recent_high:
            add("ブレイクアウト", "bullish", f"直近{lookback}本の高値 {recent_high:.2f} を上抜け")
        elif last_price < recent_low:
            add("ブレイクダウン", "bearish", f"直近{lookback}本の安値 {recent_low:.2f} を下抜け")

    return {
        "patterns": patterns,
        "support": support,
        "resistance": resistance,
        "pivot_highs": pivot_highs,
        "pivot_lows": pivot_lows,
    }

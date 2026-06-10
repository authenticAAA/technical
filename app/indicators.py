"""テクニカル指標の計算ロジック。

すべて pandas / numpy のみで実装しており、外部 API への通信は行わない。
このためネットワークなしでもユニットテストで検証できる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """単純移動平均 (Simple Moving Average)。"""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """指数平滑移動平均 (Exponential Moving Average)。"""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """相対力指数 (Relative Strength Index)。Wilder の平滑化を使用。"""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder の移動平均 = alpha 1/period の EMA
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss が 0 の場合は RSI=100
    out = out.where(avg_loss != 0, 100.0)
    return out


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD・シグナル・ヒストグラムを返す。"""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}
    )


def bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """ボリンジャーバンド (中央=SMA, 上下=±num_std)。"""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower})


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    """ストキャスティクス %K / %D。"""
    lowest = low.rolling(window=k_period, min_periods=k_period).min()
    highest = high.rolling(window=k_period, min_periods=k_period).max()
    rng = highest - lowest
    percent_k = 100.0 * (close - lowest) / rng.replace(0, np.nan)
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame({"stoch_k": percent_k, "stoch_d": percent_d})


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """平均真の値幅 (Average True Range)。Wilder 平滑化。"""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.DataFrame:
    """ADX・+DI・-DI（トレンドの強さと方向）。Wilder 平滑化。"""
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    atr_ = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_ = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return pd.DataFrame({"adx": adx_, "plus_di": plus_di, "minus_di": minus_di})


def cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """商品チャネル指数 (Commodity Channel Index)。"""
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mean_dev = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    return (tp - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))


def williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """ウィリアムズ %R（-100〜0 のオシレーター）。"""
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    rng = (highest - lowest).replace(0, np.nan)
    return -100.0 * (highest - close) / rng


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """オン・バランス・ボリューム (On-Balance Volume)。"""
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum()


def mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 14,
) -> pd.Series:
    """マネーフロー・インデックス (出来高を加味した RSI 的指標)。"""
    tp = (high + low + close) / 3.0
    raw_flow = tp * volume
    delta = tp.diff()
    pos_flow = raw_flow.where(delta > 0, 0.0)
    neg_flow = raw_flow.where(delta < 0, 0.0)
    pos_sum = pos_flow.rolling(window=period, min_periods=period).sum()
    neg_sum = neg_flow.rolling(window=period, min_periods=period).sum()
    ratio = pos_sum / neg_sum.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + ratio))
    return out.where(neg_sum != 0, 100.0)


def roc(series: pd.Series, period: int = 12) -> pd.Series:
    """変化率 (Rate of Change, %)。"""
    return 100.0 * (series / series.shift(period) - 1.0)


def parabolic_sar(
    high: pd.Series,
    low: pd.Series,
    af_step: float = 0.02,
    af_max: float = 0.2,
) -> pd.Series:
    """パラボリック SAR（トレンド転換の目安）。Wilder の標準アルゴリズム。"""
    n = len(high)
    sar = np.full(n, np.nan)
    if n < 2:
        return pd.Series(sar, index=high.index, name="psar")

    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)

    trend_up = h[1] >= h[0]
    af = af_step
    ep = h[0] if trend_up else l[0]
    sar_val = l[0] if trend_up else h[0]
    sar[0] = sar_val

    for i in range(1, n):
        sar_val = sar_val + af * (ep - sar_val)
        if trend_up:
            sar_val = min(sar_val, l[i - 1], l[max(i - 2, 0)])
            if l[i] < sar_val:  # 下降に転換
                trend_up = False
                sar_val = ep
                ep = l[i]
                af = af_step
            elif h[i] > ep:
                ep = h[i]
                af = min(af + af_step, af_max)
        else:
            sar_val = max(sar_val, h[i - 1], h[max(i - 2, 0)])
            if h[i] > sar_val:  # 上昇に転換
                trend_up = True
                sar_val = ep
                ep = h[i]
                af = af_step
            elif l[i] < ep:
                ep = l[i]
                af = min(af + af_step, af_max)
        sar[i] = sar_val

    return pd.Series(sar, index=high.index, name="psar")


def ichimoku(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    conversion: int = 9,
    base: int = 26,
    span_b: int = 52,
) -> pd.DataFrame:
    """一目均衡表（転換線・基準線・先行スパン A/B・遅行スパン）。"""

    def mid(period: int) -> pd.Series:
        hh = high.rolling(window=period, min_periods=period).max()
        ll = low.rolling(window=period, min_periods=period).min()
        return (hh + ll) / 2.0

    tenkan = mid(conversion)
    kijun = mid(base)
    senkou_a = ((tenkan + kijun) / 2.0).shift(base)
    senkou_b = mid(span_b).shift(base)
    chikou = close.shift(-base)
    return pd.DataFrame({
        "ichi_tenkan": tenkan,
        "ichi_kijun": kijun,
        "ichi_senkou_a": senkou_a,
        "ichi_senkou_b": senkou_b,
        "ichi_chikou": chikou,
    })


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV データフレームに主要指標を付与して返す。

    入力 df は 'Open','High','Low','Close','Volume' 列を持つこと。
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"] if "Volume" in df else pd.Series(0.0, index=df.index)

    out = df.copy()
    out["sma_20"] = sma(close, 20)
    out["sma_50"] = sma(close, 50)
    out["sma_200"] = sma(close, 200)
    out["ema_12"] = ema(close, 12)
    out["ema_26"] = ema(close, 26)
    out["rsi_14"] = rsi(close, 14)

    out = out.join(macd(close))
    out = out.join(bollinger_bands(close))
    out = out.join(stochastic(high, low, close))

    out["atr_14"] = atr(high, low, close)

    # 追加指標
    out = out.join(adx(high, low, close))
    out["cci_20"] = cci(high, low, close)
    out["williams_r"] = williams_r(high, low, close)
    out["obv"] = obv(close, volume)
    out["mfi_14"] = mfi(high, low, close, volume)
    out["roc_12"] = roc(close)
    out["psar"] = parabolic_sar(high, low)
    out = out.join(ichimoku(high, low, close))
    return out

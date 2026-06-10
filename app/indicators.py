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


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV データフレームに主要指標を付与して返す。

    入力 df は 'Open','High','Low','Close','Volume' 列を持つこと。
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    out = df.copy()
    out["sma_20"] = sma(close, 20)
    out["sma_50"] = sma(close, 50)
    out["sma_200"] = sma(close, 200)
    out["ema_12"] = ema(close, 12)
    out["ema_26"] = ema(close, 26)
    out["rsi_14"] = rsi(close, 14)

    macd_df = macd(close)
    out = out.join(macd_df)

    bb = bollinger_bands(close)
    out = out.join(bb)

    st = stochastic(high, low, close)
    out = out.join(st)

    out["atr_14"] = atr(high, low, close)
    return out

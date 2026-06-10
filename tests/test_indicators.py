"""指標・シグナルのユニットテスト (ネットワーク不要)。"""

import numpy as np
import pandas as pd
import pytest

from app import indicators, signals


def _make_df(closes):
    """終値列から簡易的な OHLCV データフレームを生成する。"""
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 1.0,
            "Low": closes - 1.0,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    out = indicators.sma(s, 3)
    assert np.isnan(out.iloc[0])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_ema_matches_pandas():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    out = indicators.ema(s, 2)
    expected = s.ewm(span=2, adjust=False).mean()
    pd.testing.assert_series_equal(out, expected)


def test_rsi_all_gains_is_100():
    s = pd.Series(np.arange(1, 30, dtype=float))  # 単調増加
    out = indicators.rsi(s, 14)
    assert out.dropna().iloc[-1] == pytest.approx(100.0)


def test_rsi_range_bounds():
    rng = np.random.default_rng(42)
    s = pd.Series(np.cumsum(rng.normal(size=200)) + 100)
    out = indicators.rsi(s, 14).dropna()
    assert (out >= 0).all() and (out <= 100).all()


def test_macd_columns():
    s = pd.Series(np.linspace(100, 120, 60))
    out = indicators.macd(s)
    assert list(out.columns) == ["macd", "signal", "hist"]
    # ヒストグラム = macd - signal
    np.testing.assert_allclose(
        out["hist"].values, (out["macd"] - out["signal"]).values
    )


def test_bollinger_bands_order():
    s = pd.Series(np.linspace(100, 120, 40))
    out = indicators.bollinger_bands(s, 20)
    valid = out.dropna()
    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_mid"] >= valid["bb_lower"]).all()


def test_compute_all_adds_columns():
    df = _make_df(np.linspace(100, 130, 250))
    out = indicators.compute_all(df)
    for col in ["sma_20", "sma_50", "sma_200", "rsi_14", "macd", "bb_upper", "atr_14"]:
        assert col in out.columns


def test_signals_bullish_uptrend():
    # 長期上昇トレンド -> 強気寄りになるはず
    df = _make_df(np.linspace(100, 200, 250))
    enriched = indicators.compute_all(df)
    result = signals.generate(enriched)
    assert result["verdict"] in {"BUY", "NEUTRAL"}
    assert isinstance(result["signals"], list)
    assert "score" in result


def test_signals_structure():
    df = _make_df(np.linspace(100, 110, 250))
    enriched = indicators.compute_all(df)
    result = signals.generate(enriched)
    assert set(result.keys()) == {"signals", "score", "verdict"}
    for sig in result["signals"]:
        assert set(sig.keys()) == {"name", "type", "detail"}

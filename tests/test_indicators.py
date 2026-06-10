"""指標・シグナルのユニットテスト (ネットワーク不要)。"""

import numpy as np
import pandas as pd
import pytest

from app import indicators, patterns, signals


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
    for col in [
        "sma_20", "sma_50", "sma_200", "rsi_14", "macd", "bb_upper", "atr_14",
        "adx", "plus_di", "minus_di", "cci_20", "williams_r", "obv",
        "mfi_14", "roc_12", "psar", "ichi_tenkan", "ichi_senkou_a",
    ]:
        assert col in out.columns


def test_adx_range_and_direction():
    df = _make_df(np.linspace(100, 200, 200))  # 一貫した上昇
    out = indicators.adx(df["High"], df["Low"], df["Close"])
    valid = out.dropna()
    assert (valid["adx"] >= 0).all() and (valid["adx"] <= 100).all()
    # 上昇トレンドでは +DI > -DI
    assert valid["plus_di"].iloc[-1] > valid["minus_di"].iloc[-1]


def test_williams_r_bounds():
    rng = np.random.default_rng(0)
    df = _make_df(np.cumsum(rng.normal(size=200)) + 100)
    out = indicators.williams_r(df["High"], df["Low"], df["Close"]).dropna()
    assert (out >= -100).all() and (out <= 0).all()


def test_obv_monotonic_on_uptrend():
    df = _make_df(np.linspace(100, 150, 50))  # 毎日上昇 -> OBV は単調増加
    out = indicators.obv(df["Close"], df["Volume"])
    assert (out.diff().dropna() >= 0).all()


def test_mfi_bounds():
    rng = np.random.default_rng(1)
    df = _make_df(np.cumsum(rng.normal(size=200)) + 100)
    out = indicators.mfi(df["High"], df["Low"], df["Close"], df["Volume"]).dropna()
    assert (out >= 0).all() and (out <= 100).all()


def test_roc_basic():
    s = pd.Series([100.0, 110.0])
    out = indicators.roc(s, 1)
    assert out.iloc[-1] == pytest.approx(10.0)


def test_parabolic_sar_length_and_finite():
    df = _make_df(np.linspace(100, 130, 60))
    out = indicators.parabolic_sar(df["High"], df["Low"])
    assert len(out) == len(df)
    assert np.isfinite(out.iloc[-1])


def test_ichimoku_columns():
    df = _make_df(np.linspace(100, 130, 120))
    out = indicators.ichimoku(df["High"], df["Low"], df["Close"])
    assert list(out.columns) == [
        "ichi_tenkan", "ichi_kijun", "ichi_senkou_a", "ichi_senkou_b", "ichi_chikou",
    ]


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


# ---- フォーメーション分析 ----

def _ohlc_from_close(closes):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 2.0,
            "Low": closes - 2.0,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_find_pivots_detects_peak():
    s = pd.Series([1, 2, 3, 10, 3, 2, 1], dtype=float)
    highs = patterns.find_pivots(s, left=2, right=2, kind="high")
    assert 3 in highs  # 値 10 の位置


def test_detect_returns_structure():
    df = _ohlc_from_close(np.linspace(100, 150, 120))
    res = patterns.detect(df)
    assert set(res.keys()) == {
        "patterns", "support", "resistance", "pivot_highs", "pivot_lows"
    }
    for p in res["patterns"]:
        assert set(p.keys()) == {"name", "type", "detail"}


def test_detect_uptrend_structure():
    # 高値・安値を切り上げるジグザグ -> 上昇トレンド検出
    t = np.arange(120)
    close = t * 0.5 + 6 * np.sin(t / 4.0) + 100
    df = _ohlc_from_close(close)
    res = patterns.detect(df)
    names = [p["name"] for p in res["patterns"]]
    assert "上昇トレンド" in names


def test_detect_breakout():
    # 横ばいの後に急騰 -> ブレイクアウト
    close = np.concatenate([np.full(40, 100.0), np.array([130.0])])
    df = _ohlc_from_close(close)
    res = patterns.detect(df)
    names = [p["name"] for p in res["patterns"]]
    assert "ブレイクアウト" in names

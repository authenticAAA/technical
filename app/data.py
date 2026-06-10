"""yfinance 経由での米国株データ取得とキャッシュ。"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

# 許容する期間・足の組み合わせ (yfinance の制約に準拠)
VALID_PERIODS = {
    "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max",
}
VALID_INTERVALS = {
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h",
    "1d", "5d", "1wk", "1mo", "3mo",
}

# シンプルなメモリキャッシュ: {key: (timestamp, dataframe)}
_CACHE: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}
_CACHE_TTL_SEC = 60.0


@dataclass
class FetchError(Exception):
    """データ取得に失敗した場合の例外。"""

    message: str

    def __str__(self) -> str:  # pragma: no cover
        return self.message


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance が返す MultiIndex 列を単一銘柄向けにフラット化する。"""
    if isinstance(df.columns, pd.MultiIndex):
        # (フィールド, ティッカー) または (ティッカー, フィールド) の両対応
        level0 = set(df.columns.get_level_values(0))
        if {"Open", "High", "Low", "Close"} & level0:
            df.columns = df.columns.get_level_values(0)
        else:
            df.columns = df.columns.get_level_values(-1)
    return df


def fetch_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """株価の OHLCV 履歴を取得する。

    返り値の列: Open, High, Low, Close, Volume (index は日時)。
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise FetchError("ティッカーが空です。")
    if period not in VALID_PERIODS:
        raise FetchError(f"無効な period: {period}")
    if interval not in VALID_INTERVALS:
        raise FetchError(f"無効な interval: {interval}")

    key = (ticker, period, interval)
    now = time.time()
    if use_cache and key in _CACHE:
        ts, cached = _CACHE[key]
        if now - ts < _CACHE_TTL_SEC:
            return cached.copy()

    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:  # yfinance / ネットワーク例外を集約
        raise FetchError(f"データ取得に失敗しました: {exc}") from exc

    if df is None or df.empty:
        raise FetchError(
            f"'{ticker}' のデータが見つかりません。ティッカー名を確認してください。"
        )

    df = _normalize_columns(df)
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(df.columns):
        raise FetchError(f"想定外のデータ形式です: 列={list(df.columns)}")

    df = df.dropna(subset=["Close"])
    if use_cache:
        _CACHE[key] = (now, df.copy())
    return df


def to_records(df: pd.DataFrame) -> list[dict]:
    """データフレームをフロントエンド向けの JSON シリアライズ可能なレコードに変換。

    時刻は ISO8601 文字列、数値は float / None。NaN は None に変換する。
    """
    records: list[dict] = []
    df = df.reset_index()
    time_col = df.columns[0]  # 'Date' または 'Datetime'

    for _, row in df.iterrows():
        ts = row[time_col]
        rec: dict = {"time": pd.Timestamp(ts).isoformat()}
        for col in df.columns:
            if col == time_col:
                continue
            val = row[col]
            if pd.isna(val):
                rec[col] = None
            else:
                rec[col] = float(val)
        records.append(rec)
    return records


def get_company_name(ticker: str) -> str | None:
    """銘柄の正式名称を取得 (失敗時は None)。"""
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName")
    except Exception:
        return None

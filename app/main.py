"""FastAPI アプリ本体。API エンドポイントと静的ファイルの配信。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import data as data_mod
from . import indicators, patterns, signals

app = FastAPI(title="US Stock Technical Analysis", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/analysis/{ticker}")
def analysis(
    ticker: str,
    period: str = Query("1y"),
    interval: str = Query("1d"),
) -> JSONResponse:
    """指定銘柄の OHLCV + テクニカル指標 + シグナルを返す。"""
    try:
        df = data_mod.fetch_history(ticker, period=period, interval=interval)
    except data_mod.FetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enriched = indicators.compute_all(df)
    sig = signals.generate(enriched)
    form = patterns.detect(enriched)
    name = data_mod.get_company_name(ticker.upper())

    payload = {
        "ticker": ticker.upper(),
        "name": name,
        "period": period,
        "interval": interval,
        "candles": data_mod.to_records(enriched),
        "signals": sig,
        "formations": _serialize_formations(form),
        "latest": _latest_summary(enriched),
    }
    return JSONResponse(payload)


def _serialize_formations(form: dict) -> dict:
    """フォーメーション結果を JSON シリアライズ可能な形に変換 (時刻を ISO 文字列に)。"""
    import pandas as pd

    def piv(items):
        return [
            {"time": pd.Timestamp(p["time"]).isoformat(), "price": p["price"]}
            for p in items
        ]

    return {
        "patterns": form["patterns"],
        "support": form["support"],
        "resistance": form["resistance"],
        "pivot_highs": piv(form["pivot_highs"]),
        "pivot_lows": piv(form["pivot_lows"]),
    }


def _latest_summary(df) -> dict:
    """最新バーの主要値をまとめる。"""
    last = df.iloc[-1]

    def g(col):
        val = last.get(col)
        try:
            import pandas as pd

            return None if pd.isna(val) else float(val)
        except Exception:
            return None

    return {
        "close": g("Close"),
        "rsi_14": g("rsi_14"),
        "macd": g("macd"),
        "macd_signal": g("signal"),
        "sma_20": g("sma_20"),
        "sma_50": g("sma_50"),
        "sma_200": g("sma_200"),
        "atr_14": g("atr_14"),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# 静的ファイル (JS/CSS) の配信
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 📈 米国株テクニカル分析アプリ

Yahoo Finance (yfinance) から米国株のチャートを自動取得し、主要なテクニカル指標と
売買シグナルをブラウザ上で可視化する Web アプリです。

## 特徴

- **自動データ取得**: ティッカーを入力するだけで OHLCV データを取得（API キー不要）
- **テクニカル指標**: SMA(20/50/200)、EMA、RSI、MACD、ボリンジャーバンド、ストキャスティクス、ATR
- **売買シグナル**: ゴールデン/デッドクロス、RSI 過熱、MACD クロスなどを総合スコア化し `BUY / SELL / NEUTRAL` を判定
- **インタラクティブチャート**: TradingView lightweight-charts によるローソク足 + 指標オーバーレイ。価格 / RSI / MACD の各ペインが時間軸同期

## 技術スタック

| 領域 | 使用技術 |
|------|----------|
| バックエンド | Python 3.11, FastAPI, Uvicorn |
| データ取得 | yfinance (Yahoo Finance) |
| 指標計算 | pandas / numpy（自前実装・外部 TA ライブラリ不要） |
| フロントエンド | 素の HTML/CSS/JS + lightweight-charts (CDN) |

## セットアップ

```bash
# 依存関係のインストール（仮想環境推奨）
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

```bash
uvicorn app.main:app --reload
```

ブラウザで http://127.0.0.1:8000 を開き、ティッカー（例: `AAPL`, `MSFT`, `NVDA`）を
入力して「分析」を押すとチャートとシグナルが表示されます。

> ⚠️ Yahoo Finance への通信が必要です。ネットワーク制限のある環境では取得に失敗します。

## API

| エンドポイント | 説明 |
|----------------|------|
| `GET /` | フロントエンド (HTML) |
| `GET /api/health` | ヘルスチェック |
| `GET /api/analysis/{ticker}?period=1y&interval=1d` | OHLCV + 指標 + シグナルを JSON で返す |

`period`: `1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max`
`interval`: `1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo`

### レスポンス例（抜粋）

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "candles": [{ "time": "2024-01-02T00:00:00", "Open": 187.1, "Close": 185.6, "rsi_14": 52.3, "macd": 1.2, "...": "..." }],
  "signals": { "verdict": "BUY", "score": 4, "signals": [{ "name": "ゴールデンクロス", "type": "bullish", "detail": "SMA50 が SMA200 を上抜け" }] },
  "latest": { "close": 185.6, "rsi_14": 52.3, "sma_200": 178.4 }
}
```

## テスト

指標・シグナルのロジックはネットワーク不要のユニットテストで検証できます。

```bash
pip install pytest
python -m pytest tests/ -q
```

## プロジェクト構成

```
technical/
├── app/
│   ├── main.py          # FastAPI ルーティング・静的配信
│   ├── data.py          # yfinance データ取得 + キャッシュ
│   ├── indicators.py    # テクニカル指標計算
│   ├── signals.py       # 売買シグナル判定
│   └── static/          # フロントエンド (HTML/CSS/JS)
├── tests/
│   └── test_indicators.py
└── requirements.txt
```

## 免責事項

本アプリは教育・情報提供を目的としたものであり、投資助言ではありません。
投資判断はご自身の責任で行ってください。

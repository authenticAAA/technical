"use strict";

// ---- DOM ----
const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const analyzeBtn = $("analyze");

// ---- チャート初期化 ----
const chartOpts = {
  layout: { background: { color: "#161b22" }, textColor: "#e6edf3" },
  grid: {
    vertLines: { color: "#21262d" },
    horzLines: { color: "#21262d" },
  },
  rightPriceScale: { borderColor: "#2a313c" },
  timeScale: { borderColor: "#2a313c", timeVisible: true, secondsVisible: false },
  crosshair: { mode: 0 },
};

const priceChart = LightweightCharts.createChart($("price-chart"), chartOpts);
const rsiChart = LightweightCharts.createChart($("rsi-chart"), chartOpts);
const macdChart = LightweightCharts.createChart($("macd-chart"), chartOpts);

// 価格チャートのシリーズ
const candleSeries = priceChart.addCandlestickSeries({
  upColor: "#26a69a", downColor: "#ef5350",
  borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350",
});
const sma20 = priceChart.addLineSeries({ color: "#f1c40f", lineWidth: 1, title: "SMA20" });
const sma50 = priceChart.addLineSeries({ color: "#58a6ff", lineWidth: 1, title: "SMA50" });
const sma200 = priceChart.addLineSeries({ color: "#e056fd", lineWidth: 1, title: "SMA200" });
const bbUpper = priceChart.addLineSeries({ color: "rgba(139,148,158,0.6)", lineWidth: 1, lineStyle: 2 });
const bbLower = priceChart.addLineSeries({ color: "rgba(139,148,158,0.6)", lineWidth: 1, lineStyle: 2 });
const volumeSeries = priceChart.addHistogramSeries({
  priceFormat: { type: "volume" },
  priceScaleId: "vol",
});
priceChart.priceScale("vol").applyOptions({
  scaleMargins: { top: 0.8, bottom: 0 },
});

// RSI チャート
const rsiSeries = rsiChart.addLineSeries({ color: "#58a6ff", lineWidth: 1 });
const rsi70 = rsiChart.addLineSeries({ color: "rgba(239,83,80,0.5)", lineWidth: 1, lineStyle: 2 });
const rsi30 = rsiChart.addLineSeries({ color: "rgba(38,166,154,0.5)", lineWidth: 1, lineStyle: 2 });

// MACD チャート
const macdLine = macdChart.addLineSeries({ color: "#58a6ff", lineWidth: 1 });
const macdSignal = macdChart.addLineSeries({ color: "#f1c40f", lineWidth: 1 });
const macdHist = macdChart.addHistogramSeries({});

// ---- 時間軸の同期 ----
const charts = [priceChart, rsiChart, macdChart];
let syncing = false;
charts.forEach((src) => {
  src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (syncing || !range) return;
    syncing = true;
    charts.forEach((dst) => {
      if (dst !== src) dst.timeScale().setVisibleLogicalRange(range);
    });
    syncing = false;
  });
});

// ---- ユーティリティ ----
const toTime = (iso) => Math.floor(Date.parse(iso) / 1000);

function line(candles, field) {
  const out = [];
  for (const c of candles) {
    if (c[field] !== null && c[field] !== undefined) {
      out.push({ time: toTime(c.time), value: c[field] });
    }
  }
  return out;
}

function constLine(candles, value) {
  return candles
    .filter((c) => c.Close !== null)
    .map((c) => ({ time: toTime(c.time), value }));
}

function fmt(v, d = 2) {
  return v === null || v === undefined ? "—" : Number(v).toLocaleString("en-US", {
    minimumFractionDigits: d, maximumFractionDigits: d,
  });
}

// ---- 描画 ----
function render(payload) {
  const candles = payload.candles;

  candleSeries.setData(candles.map((c) => ({
    time: toTime(c.time), open: c.Open, high: c.High, low: c.Low, close: c.Close,
  })));

  volumeSeries.setData(candles.map((c) => ({
    time: toTime(c.time),
    value: c.Volume ?? 0,
    color: c.Close >= c.Open ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
  })));

  sma20.setData(line(candles, "sma_20"));
  sma50.setData(line(candles, "sma_50"));
  sma200.setData(line(candles, "sma_200"));
  bbUpper.setData(line(candles, "bb_upper"));
  bbLower.setData(line(candles, "bb_lower"));

  rsiSeries.setData(line(candles, "rsi_14"));
  rsi70.setData(constLine(candles, 70));
  rsi30.setData(constLine(candles, 30));

  macdLine.setData(line(candles, "macd"));
  macdSignal.setData(line(candles, "signal"));
  macdHist.setData(candles
    .filter((c) => c.hist !== null && c.hist !== undefined)
    .map((c) => ({
      time: toTime(c.time),
      value: c.hist,
      color: c.hist >= 0 ? "rgba(38,166,154,0.6)" : "rgba(239,83,80,0.6)",
    })));

  priceChart.timeScale().fitContent();
  renderSummary(payload);
}

function renderSummary(payload) {
  const s = payload.signals;
  const l = payload.latest;

  $("verdict").textContent = s.verdict;
  $("verdict").className = "verdict " + s.verdict;

  const metrics = [
    ["終値", "$" + fmt(l.close)],
    ["RSI(14)", fmt(l.rsi_14, 1)],
    ["MACD", fmt(l.macd, 3)],
    ["SMA20", "$" + fmt(l.sma_20)],
    ["SMA50", "$" + fmt(l.sma_50)],
    ["SMA200", "$" + fmt(l.sma_200)],
    ["ATR(14)", fmt(l.atr_14)],
    ["スコア", String(s.score)],
  ];
  $("metrics").innerHTML = metrics.map(([k, v]) =>
    `<div class="metric"><span class="label">${k}</span><span class="value">${v}</span></div>`
  ).join("");

  $("signal-list").innerHTML = s.signals.map((sig) =>
    `<span class="chip ${sig.type}">${sig.name}: ${sig.detail}</span>`
  ).join("") || '<span class="chip neutral">明確なシグナルなし</span>';

  $("summary").classList.remove("hidden");
}

// ---- データ取得 ----
async function analyze() {
  const ticker = $("ticker").value.trim().toUpperCase();
  if (!ticker) return;
  const period = $("period").value;
  const interval = $("interval").value;

  analyzeBtn.disabled = true;
  statusEl.className = "status";
  statusEl.textContent = `${ticker} を取得中...`;

  try {
    const res = await fetch(`/api/analysis/${encodeURIComponent(ticker)}?period=${period}&interval=${interval}`);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || "取得に失敗しました");
    render(body);
    const name = body.name ? `${body.name} (${body.ticker})` : body.ticker;
    statusEl.textContent = `${name} — ${body.candles.length} 本のローソク足`;
  } catch (err) {
    statusEl.className = "status error";
    statusEl.textContent = "エラー: " + err.message;
  } finally {
    analyzeBtn.disabled = false;
  }
}

analyzeBtn.addEventListener("click", analyze);
$("ticker").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });

// リサイズ対応
window.addEventListener("resize", () => {
  charts.forEach((c, i) => {
    const el = [$("price-chart"), $("rsi-chart"), $("macd-chart")][i];
    c.applyOptions({ width: el.clientWidth });
  });
});

// 初回ロード
analyze();

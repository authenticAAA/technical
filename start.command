#!/bin/bash
# Mac 用ダブルクリック起動スクリプト
cd "$(dirname "$0")"
echo "================================================"
echo "  米国株テクニカル分析アプリ を起動します"
echo "================================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "[エラー] Python3 が見つかりません。"
  echo "https://www.python.org/downloads/ からインストールしてください。"
  echo
  read -n 1 -s -r -p "何かキーを押すと閉じます..."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "初回セットアップ中です（少し時間がかかります）..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo
echo "ブラウザで http://localhost:8501 が開きます。"
echo "終了するには、このウィンドウを閉じてください。"
echo
streamlit run streamlit_app.py

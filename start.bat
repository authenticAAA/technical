@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   米国株テクニカル分析アプリ を起動します
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [エラー] Python が見つかりません。
  echo https://www.python.org/downloads/ からインストールしてください。
  echo インストール時に "Add Python to PATH" に必ずチェックを入れてください。
  echo.
  pause
  exit /b 1
)

if not exist .venv (
  echo 初回セットアップ中です（少し時間がかかります）...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo ブラウザで http://localhost:8501 が開きます。
echo 終了するには、この黒い画面を閉じてください。
echo.
streamlit run streamlit_app.py
pause

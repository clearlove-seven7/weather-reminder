@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  本地运行：检测到降水才会推送微信
echo  （需要本机装有 Python 3.9+，纯标准库无依赖）
echo ============================================
python main.py
echo.
pause

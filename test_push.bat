@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  发送一条测试消息到微信（先填好token）
echo  （需要本机装有 Python 3.9+，纯标准库无依赖）
echo ============================================
python main.py --test
echo.
pause

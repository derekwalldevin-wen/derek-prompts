@echo off
chcp 65001 >nul
cd /d "%~dp0site"
echo 正在启动本地预览 http://127.0.0.1:8765/
echo 关闭这个窗口即停止服务。
start "" "http://127.0.0.1:8765/"
python -m http.server 8765

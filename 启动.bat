@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OpenCode Token Daily V1.0.0-20261122
echo.
echo   OpenCode Token Daily  V1.0.0-20261122
echo   正在启动本地服务，浏览器将自动打开...
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py server.py
) else (
  python server.py
)
echo.
pause

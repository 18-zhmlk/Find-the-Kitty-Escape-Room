@echo off
chcp 65001 >nul
title RobloxVoiceGesture - Installation

cd /d "%~dp0"

echo =========================================
echo   RobloxVoiceGesture - Установка
echo =========================================
echo.

echo [1/4] Проверка Python...
py -3.9 --version
if errorlevel 1 (
    echo.
    echo Python 3.9 не установлен!
    echo Установите Python 3.9.13 x64.
    pause
    exit /b
)

echo.
echo [2/4] Создание виртуального окружения...

if not exist ".venv\Scripts\python.exe" (
    py -3.9 -m venv .venv
)

echo.
echo [3/4] Обновление pip...

.venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo [4/4] Установка библиотек...

.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo =========================================
echo   УСТАНОВКА ЗАВЕРШЕНА!
echo =========================================
pause

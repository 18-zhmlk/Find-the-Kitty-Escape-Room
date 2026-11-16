
@echo off
chcp 65001 >nul
title RobloxVoiceGesture

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Сначала запустите install.bat!
    pause
    exit /b
)

if not exist "vosk-model-small-ru-0.22\am" (
    echo Не найдена модель русского голоса Vosk!
    echo Распакуйте vosk-model-small-ru-0.22 в папку проекта.
    pause
    exit /b
)

echo Запуск RobloxVoiceGesture...
echo.

.venv\Scripts\python.exe gesture_control.py

pause

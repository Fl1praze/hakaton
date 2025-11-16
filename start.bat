@echo off
REM Скрипт быстрого запуска для Windows

echo ==========================================
echo   Запуск PDF Parser API
echo ==========================================
echo.

REM Проверка Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker не установлен!
    echo Установите Docker: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

echo ✅ Docker найден
echo.

REM Создание .env если не существует
if not exist .env (
    echo 📝 Создание .env файла...
    copy .env.example .env
)

REM Запуск
echo 🚀 Запуск контейнеров...
docker-compose up --build

echo.
echo ==========================================
echo   API доступен по адресу:
echo   http://localhost:8000
echo   Документация: http://localhost:8000/docs
echo ==========================================
pause


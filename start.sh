#!/bin/bash

# Скрипт быстрого запуска для Linux/Mac

echo "=========================================="
echo "  Запуск PDF Parser API"
echo "=========================================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    echo "Установите Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker найден"
echo ""

# Создание .env если не существует
if [ ! -f .env ]; then
    echo "📝 Создание .env файла..."
    cp .env.example .env
fi

# Запуск
echo "🚀 Запуск контейнеров..."
docker-compose up --build

echo ""
echo "=========================================="
echo "  API доступен по адресу:"
echo "  http://localhost:8000"
echo "  Документация: http://localhost:8000/docs"
echo "=========================================="


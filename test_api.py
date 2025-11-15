"""
Скрипт для быстрого тестирования API
"""

import requests
import sys
from pathlib import Path

API_URL = "http://localhost:8000"

def test_health():
    """Проверка работоспособности API"""
    print("🔍 Проверка health endpoint...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API работает!")
            return True
        else:
            print(f"❌ API вернул статус {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ API не доступен. Запустите сервер:")
        print("   docker-compose up")
        print("   или: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_process_pdf(pdf_path):
    """Тестирование обработки PDF файла"""
    if not Path(pdf_path).exists():
        print(f"❌ Файл не найден: {pdf_path}")
        return False
    
    print(f"\n📄 Тестирование обработки: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            response = requests.post(f"{API_URL}/api/process_pdf/", files=files)
        
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Успешно обработано!")
            print(f"   Данные: {data.get('data', {})}")
            return True
        else:
            print(f"❌ Ошибка: {response.json()}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def main():
    print("="*60)
    print("  Тестирование PDF Parser API")
    print("="*60)
    print()
    
    # Тест 1: Health check
    if not test_health():
        sys.exit(1)
    
    # Тест 2: Обработка PDF
    pdf_folder = Path("app/notebooks")
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print("\n⚠️ PDF файлы не найдены в app/notebooks/")
        print("   Добавьте тестовые PDF файлы для проверки")
        return
    
    print(f"\n📁 Найдено {len(pdf_files)} PDF файлов")
    
    # Тестируем первый файл
    test_process_pdf(pdf_files[0])
    
    print("\n" + "="*60)
    print("  Тестирование завершено!")
    print("="*60)
    print(f"\n📚 Документация: {API_URL}/docs")
    print(f"🏥 Health check: {API_URL}/health")


if __name__ == "__main__":
    main()


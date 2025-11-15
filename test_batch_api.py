"""
Скрипт для тестирования batch обработки PDF через API

Использование:
    python test_batch_api.py file1.pdf file2.pdf file3.pdf
"""

import sys
import requests
from pathlib import Path


def test_batch_processing(file_paths):
    """
    Отправляет несколько PDF файлов на batch обработку
    """
    # URL API
    url = "http://localhost:8000/api/process-batch/"
    
    print(f"\n🚀 Отправка {len(file_paths)} файлов на batch обработку...\n")
    
    # Подготовка файлов
    files = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Файл не найден: {file_path}")
            continue
        
        if not path.suffix.lower() == '.pdf':
            print(f"⚠️  Пропускаем {file_path} (не PDF)")
            continue
        
        files.append(
            ('files', (path.name, open(path, 'rb'), 'application/pdf'))
        )
    
    if not files:
        print("❌ Нет валидных PDF файлов для отправки")
        return
    
    try:
        # Отправка запроса
        response = requests.post(url, files=files)
        
        # Закрываем файлы
        for _, file_tuple in files:
            file_tuple[1].close()
        
        # Проверка ответа
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ Batch обработка завершена!")
            print(f"📊 Статистика:")
            print(f"   • Всего файлов: {result['total']}")
            print(f"   • Успешно: {result['successful']}")
            print(f"   • Ошибок: {result['failed']}")
            print()
            
            # Результаты по каждому файлу
            for idx, item in enumerate(result['results'], 1):
                print(f"📄 {idx}. {item['filename']}")
                
                if item['status'] == 'success':
                    data = item['data']
                    print(f"   ✅ Статус: Успешно")
                    print(f"   📋 ИНН: {data.get('inn', 'N/A')}")
                    print(f"   🏢 Поставщик: {data.get('vendor', 'N/A')}")
                    print(f"   📅 Дата: {data.get('date', 'N/A')}")
                    print(f"   💰 Сумма: {data.get('total', 'N/A')} руб.")
                    print(f"   🤖 Метод: {data.get('method', 'N/A')}")
                else:
                    print(f"   ❌ Статус: Ошибка")
                    print(f"   ⚠️  {item['error']}")
                print()
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"Ответ: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к API")
        print("Убедитесь, что API запущен: docker-compose up -d")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def test_single_file(file_path):
    """
    Отправляет 1 PDF файл на обработку (single endpoint)
    """
    url = "http://localhost:8000/api/process_pdf/"
    
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Файл не найден: {file_path}")
        return
    
    print(f"\n🚀 Отправка файла {path.name}...\n")
    
    try:
        with open(path, 'rb') as f:
            files = {'file': (path.name, f, 'application/pdf')}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            data = result['data']
            
            print(f"✅ Файл успешно обработан!")
            print(f"\n📋 Извлечённые данные:")
            print(f"   • ИНН: {data.get('inn', 'N/A')}")
            print(f"   • Поставщик: {data.get('vendor', 'N/A')}")
            print(f"   • Номер счёта: {data.get('invoice_number', 'N/A')}")
            print(f"   • Дата: {data.get('date', 'N/A')}")
            print(f"   • Сумма: {data.get('total', 'N/A')} руб.")
            print(f"   • Телефон: {data.get('phone', 'N/A')}")
            print(f"   • Email: {data.get('email', 'N/A')}")
            print(f"   • Адрес: {data.get('address', 'N/A')}")
            print(f"\n🤖 Метод обработки: {data.get('method', 'N/A')}")
            if 'model_accuracy' in data:
                print(f"📊 Точность модели: {data['model_accuracy']}")
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"Ответ: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к API")
        print("Убедитесь, что API запущен: docker-compose up -d")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Использование:")
        print("   python test_batch_api.py file1.pdf file2.pdf file3.pdf")
        print("\n   или")
        print("   python test_batch_api.py single invoice.pdf")
        sys.exit(1)
    
    # Проверка режима
    if sys.argv[1] == "single" and len(sys.argv) == 3:
        # Single file mode
        test_single_file(sys.argv[2])
    else:
        # Batch mode
        test_batch_processing(sys.argv[1:])


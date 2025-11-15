"""
АВТОМАТИЧЕСКОЕ ИЗВЛЕЧЕНИЕ ОБУЧАЮЩИХ ДАННЫХ ИЗ PDF

Этот скрипт:
1. Находит все PDF файлы в папке pdf_for_study/
2. Извлекает из них текст (с OCR для сканов)
3. Создает обучающие данные с реальными значениями
4. Сохраняет данные для обучения модели

Как работает:
- Использует processor.py для извлечения текста
- Применяет regex для извлечения данных
- Проверяет что данные корректные
- Создает список готовых примеров

КАК ЗАПУСТИТЬ:
    cd app
    python auto_extract_training_data.py
"""

import sys                    
from pathlib import Path      
import json                   
import re                     

# Добавляем текущую папку в пути Python чтобы импортировать наши модули
sys.path.append('.')

# Импортируем наши функции для работы с PDF
from processor import extract_text_from_pdf


# ФУНКЦИЯ: Извлечение данных из текста
def extract_data_from_text(text):
    """
    Извлекает ИНН, название, дату и сумму из текста чека
    
    Параметры:
        text (str): Текст чека из PDF
        
    Возвращает:
        dict: Словарь с извлеченными данными
              Пример: {'inn': '1234567890', 'vendor': 'ООО Компания', ...}
    """
    
    # Создаем пустой словарь для результатов
    data = {}
    
    # 1. ИЗВЛЕЧЕНИЕ ИНН (10 или 12 цифр после слова "ИНН")
    inn_match = re.search(r"ИНН[:\s]*(\d{10,12})", text, re.IGNORECASE)
    if inn_match:
        print(inn_match)
        data['inn'] = inn_match.group(1)  # .group(1) возвращает содержимое скобок ()
    
    # 2. ИЗВЛЕЧЕНИЕ НАЗВАНИЯ ОРГАНИЗАЦИИ
    vendor_match = re.search(r"(ООО\s+[\"«]?[^\"»\n]+[\"»]?)", text)
    if not vendor_match:
        vendor_match = re.search(r"(АО\s+[\"«]?[^\"»\n]+[\"»]?)", text)
    if not vendor_match:
        vendor_match = re.search(
            r"(ИП\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)", 
            text
        )
    if vendor_match:
        vendor = vendor_match.group(1).strip()
        vendor = vendor.replace('«', '').replace('»', '').replace('"', '')
        data['vendor'] = vendor
    
    # 3. ИЗВЛЕЧЕНИЕ ДАТЫ (разные форматы)
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
    
    if not date_match:
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    
    if not date_match:
        date_match = re.search(
            r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})", 
            text, 
            re.IGNORECASE
        )

    if not date_match:
        date_match = re.search(
            r"(\d{1,2}\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)\s+\d{4})", 
            text, 
            re.IGNORECASE
        )
    
    if date_match:
        data['date'] = date_match.group(1)
    
    # 4. ИЗВЛЕЧЕНИЕ СУММЫ (УЛУЧШЕННАЯ ВЕРСИЯ)
    total_match = re.search(
        r"(?:Итого|ИТОГО|Всего|ВСЕГО|К оплате|Сумма|СУММА|итог|total)[:\s=]*([\d\s]+[.,]\d{1,2})", 
        text, 
        re.IGNORECASE
    )
    
    if not total_match:
        # = в начале, потом цифры с точкой/запятой
        total_match = re.search(r"[=]\s*([\d\s]+[.,]\d{1,2})", text)
    
 
    if not total_match:
        # Ищем все числа вида 123.45 или 1234,56 (больше 10 рублей)
        all_amounts = re.findall(r"\b(\d{2,}[.,]\d{1,2})\b", text)
        
        if all_amounts:
            try:
                amounts_as_float = []
                for amt in all_amounts:
                    clean_amt = amt.replace(',', '.')
                    try:
                        amounts_as_float.append(float(clean_amt))
                    except:
                        pass
                
                if amounts_as_float:
                    max_amount = max(amounts_as_float)
                    if max_amount >= 1.0:
                        data['total'] = max_amount
            except:
                pass
    
    
    if total_match:
        amount_str = total_match.group(1)
        amount_str = amount_str.replace(' ', '')
        amount_str = amount_str.replace(',', '.')

        try:
            data['total'] = float(amount_str)
        except ValueError:
            # Если не получилось - сохраняем как строку
            data['total'] = amount_str
    
    return data



# ФУНКЦИЯ: Обработка одного PDF файла
def process_pdf_file(pdf_path):
    """
    Обрабатывает один PDF файл и извлекает из него данные  
    Возвращает:
        tuple: (текст_для_обучения, словарь_с_данными)
               или (None, None) если не удалось обработать
    """
    
    # Выводим имя файла который обрабатываем
    print(f"📄 Обработка: {pdf_path.name}")
    try:
        #Читаем содержимое PDF файла как байты
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()  # Читаем весь файл в память
        # Шаг 2: Извлекаем текст из PDF (с OCR если нужно)
        text = extract_text_from_pdf(pdf_bytes)
 
        if not text or len(text.strip()) < 20:
            print(f"   ⚠️ Мало текста, пропускаем")
            return None, None
        
        # Шаг 3: Извлекаем структурированные данные из текста
        data = extract_data_from_text(text)
        # Проверяем что извлекли хоть что-то важное
        if not data.get('inn') and not data.get('vendor'):
            print(f"   ⚠️ Не нашли ИНН или название, пропускаем")
            return None, None
        # Шаг 4: Создаем краткую версию текста для обучения
        training_text = ' '.join(text[:500].split())
        
        # Выводим что извлекли
        print(f"   ✅ ИНН: {data.get('inn', 'N/A')}")
        print(f"   ✅ Название: {data.get('vendor', 'N/A')}")
        print(f"   ✅ Дата: {data.get('date', 'N/A')}")
        print(f"   ✅ Сумма: {data.get('total', 'N/A')}")
        
        # Возвращаем текст и данные
        return training_text, data
        
    except Exception as e:
        # Если произошла ошибка - выводим и пропускаем файл
        print(f"   ❌ Ошибка: {e}")
        return None, None


# ГЛАВНАЯ ФУНКЦИЯ
def main():
    """
    Главная функция - обрабатывает все PDF и создает обучающие данные
    """
    # Выводим заголовок
    print("="*70)
    print("АВТОМАТИЧЕСКОЕ ИЗВЛЕЧЕНИЕ ОБУЧАЮЩИХ ДАННЫХ ИЗ PDF")
    print("="*70)
    print()

    pdf_folder = Path(__file__).parent / 'pdf_for_study'
    
    if not pdf_folder.exists():
        print(f"❌ ОШИБКА: Папка {pdf_folder} не найдена!")
        print("   Создайте папку: app/pdf_for_study/")
        print("   И добавьте туда PDF файлы для обучения")
        return
    
    pdf_files = list(pdf_folder.glob('*.pdf'))
    
    print(f"🔍 Найдено PDF файлов: {len(pdf_files)}")
    print()
    # Шаг 2: Обрабатываем каждый PDF файл
    training_data = []
    # Перебираем все найденные PDF файлы
    for pdf_file in pdf_files:

        text, data = process_pdf_file(pdf_file)
        if text and data:
            # Создаем кортеж (tuple): (текст, данные)
            training_example = (text, data)
            training_data.append(training_example)
        print()
    # Шаг 3: Сохраняем результаты
    print("="*70)
    print(f"✅ Успешно обработано: {len(training_data)} файлов")
    print("="*70)
    print()
    # Сохраняем в JSON файл для просмотра
    output_file = Path(__file__).parent / 'training_data.json'
    # Преобразуем в формат JSON (словари вместо кортежей)
    json_data = [
        {
            'text': text,
            'data': data
        }
        for text, data in training_data
    ]
    # Записываем в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Данные сохранены в: {output_file}")
    print()
    # Шаг 4: Выводим статистику
    print("📊 СТАТИСТИКА:")
    print(f"   - Всего PDF: {len(pdf_files)}")
    print(f"   - Успешно: {len(training_data)}")
    print(f"   - Пропущено: {len(pdf_files) - len(training_data)}")
    
    fields_found = {
        'inn': 0,
        'vendor': 0,
        'date': 0,
        'total': 0
    }

    for text, data in training_data:
        for field in fields_found.keys():
            if field in data:
                fields_found[field] += 1
    
    print()
    print("📋 Найдено полей:")
    for field, count in fields_found.items():
        percentage = (count / len(training_data) * 100) if training_data else 0
        print(f"   - {field:10s}: {count:3d} ({percentage:.1f}%)")
    
    return training_data


# ТОЧКА ВХОДА - запускается когда файл запускают напрямую
if __name__ == "__main__":
    # Вызываем главную функцию
    training_data = main()
    
    print()
    print("="*70)
    print("✅ ГОТОВО!")
    print("="*70)
    print()
    print("Теперь можете использовать эти данные для обучения модели")
    print("Запустите: python train_and_save_model.py")


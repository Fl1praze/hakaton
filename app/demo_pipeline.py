"""
Демонстрация работы пайплайна обработки PDF счетов

Этот скрипт демонстрирует:
1. Работу пайплайна извлечения данных из PDF
2. Точность распознавания на тестовых данных
3. Примеры успешной и неуспешной обработки
"""

import json
from pathlib import Path
from processor import extract_invoice_data, extract_text_from_pdf


def test_single_pdf(pdf_path: Path):
    """Тестирование одного PDF файла"""
    print(f"\n{'='*60}")
    print(f"Обработка файла: {pdf_path.name}")
    print(f"{'='*60}\n")
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    # Извлекаем текст
    text = extract_text_from_pdf(pdf_bytes)
    print("=== ИЗВЛЕЧЕННЫЙ ТЕКСТ (первые 500 символов) ===")
    print(text[:500])
    print(f"\nВсего символов: {len(text)}\n")
    
    # Обрабатываем и получаем структурированные данные
    result = extract_invoice_data(pdf_bytes)
    print("=== ИЗВЛЕЧЕННЫЕ ДАННЫЕ ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return result


def test_all_pdfs(pdf_folder: Path):
    """Массовое тестирование всех PDF файлов"""
    pdf_files = list(pdf_folder.glob('*.pdf'))
    
    print(f"\n{'='*60}")
    print(f"Найдено PDF файлов: {len(pdf_files)}")
    print(f"{'='*60}\n")
    
    results = []
    
    for pdf_file in pdf_files:
        try:
            with open(pdf_file, 'rb') as f:
                pdf_bytes = f.read()
            
            data = extract_invoice_data(pdf_bytes)
            
            success = 'error' not in data
            results.append({
                'filename': pdf_file.name,
                'success': success,
                'data': data
            })
            
            status = "✓" if success else "✗"
            print(f"{status} {pdf_file.name}")
            
        except Exception as e:
            results.append({
                'filename': pdf_file.name,
                'success': False,
                'error': str(e)
            })
            print(f"✗ {pdf_file.name} - Ошибка: {e}")
    
    # Статистика
    print(f"\n{'='*60}")
    print("СТАТИСТИКА")
    print(f"{'='*60}")
    print(f"Обработано файлов: {len(results)}")
    print(f"Успешно: {sum(1 for r in results if r['success'])}")
    print(f"С ошибками: {sum(1 for r in results if not r['success'])}")
    
    return results


def calculate_metrics(results):
    """Вычисление метрик качества"""
    
    # Эталонные данные для проверки (пример)
    ground_truth = {
        'Mail.ru Письмо от info@ofd-magnit.ru.pdf': {
            'inn': '2310031475',
            'vendor': 'ТАНДЕР',
            'date': '27.09.2025',
            'total': 692.88
        },
    }
    
    print(f"\n{'='*60}")
    print("МЕТРИКИ КАЧЕСТВА")
    print(f"{'='*60}\n")
    
    field_stats = {
        'inn': {'correct': 0, 'total': 0},
        'vendor': {'correct': 0, 'total': 0},
        'date': {'correct': 0, 'total': 0},
        'total': {'correct': 0, 'total': 0}
    }
    
    for result in results:
        if not result['success']:
            continue
            
        filename = result['filename']
        if filename not in ground_truth:
            continue
        
        truth = ground_truth[filename]
        data = result['data']
        
        for field in field_stats.keys():
            if field in truth:
                field_stats[field]['total'] += 1
                
                predicted = str(data.get(field, 'UNRECOGNIZED'))
                actual = str(truth[field])
                
                # Проверка на совпадение (с учетом частичных совпадений)
                if predicted == actual or predicted in actual or actual in predicted:
                    field_stats[field]['correct'] += 1
    
    # Вывод метрик
    for field, stats in field_stats.items():
        if stats['total'] > 0:
            accuracy = (stats['correct'] / stats['total']) * 100
            print(f"{field:15s}: {accuracy:.1f}% ({stats['correct']}/{stats['total']})")
        else:
            print(f"{field:15s}: N/A (нет данных для проверки)")
    
    # Общая точность
    total_correct = sum(s['correct'] for s in field_stats.values())
    total_count = sum(s['total'] for s in field_stats.values())
    
    if total_count > 0:
        overall_accuracy = (total_correct / total_count) * 100
        print(f"\nОбщая точность: {overall_accuracy:.1f}%")


def print_summary_table(results):
    """Вывод сводной таблицы результатов"""
    print(f"\n{'='*80}")
    print("СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print(f"{'='*80}\n")
    
    # Заголовок таблицы
    print(f"{'Файл':<40} {'✓/✗':<5} {'ИНН':<15} {'Дата':<12} {'Сумма':<10}")
    print("-" * 80)
    
    for r in results:
        filename = r['filename'][:38]
        status = '✓' if r['success'] else '✗'
        
        if r['success']:
            inn = str(r['data'].get('inn', 'N/A'))[:13]
            date = str(r['data'].get('date', 'N/A'))[:10]
            total = str(r['data'].get('total', 'N/A'))[:8]
        else:
            inn = date = total = 'N/A'
        
        print(f"{filename:<40} {status:<5} {inn:<15} {date:<12} {total:<10}")


def main():
    """Главная функция"""
    print("="*60)
    print("ДЕМОНСТРАЦИЯ ПАЙПЛАЙНА ОБРАБОТКИ PDF СЧЕТОВ")
    print("="*60)
    
    # Путь к папке с PDF файлами
    pdf_folder = Path(__file__).parent / 'notebooks'
    
    if not pdf_folder.exists():
        print(f"⚠️ Папка {pdf_folder} не найдена")
        return
    
    pdf_files = list(pdf_folder.glob('*.pdf'))
    
    if not pdf_files:
        print(f"⚠️ PDF файлы не найдены в {pdf_folder}")
        return
    
    # Тест 1: Один файл подробно
    test_single_pdf(pdf_files[0])
    
    # Тест 2: Все файлы
    results = test_all_pdfs(pdf_folder)
    
    # Тест 3: Сводная таблица
    print_summary_table(results)
    
    # Тест 4: Метрики качества
    calculate_metrics(results)
    
    print("\n" + "="*60)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("="*60)


if __name__ == "__main__":
    main()


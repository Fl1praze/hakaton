import fitz 
import pytesseract 
from PIL import Image 
import io
import re 
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import os
import platform

# небольшой хелпер: ищем tesseract под windows
if platform.system() == 'Windows':
    # основной путь установки
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"[OK] Tesseract найден: {tesseract_path}")
    else:
        alt_paths = [
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Tesseract-OCR\tesseract.exe',
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                pytesseract.pytesseract.tesseract_cmd = alt_path
                print(f"[OK] Tesseract найден: {alt_path}")
                break
        else:
            print("[WARNING] tesseract не найден, ocr работать не будет")
            print("   https://github.com/UB-Mannheim/tesseract/wiki")


HYBRID_BERT_MODEL = None

try:
    try:
        from app.hybrid_bert_model import HybridBERTExtractor
        print("[OK] Импортирован HybridBERTExtractor (API режим)")
    except ImportError:
        # fallback для запуска из jupyter
        from hybrid_bert_model import HybridBERTExtractor
        print("[OK] Импортирован HybridBERTExtractor (Jupyter режим)")
    
    # создаем одну общую инстанцию
    print("[INFO] инициализация гибридной bert модели...")
    HYBRID_BERT_MODEL = HybridBERTExtractor()
    
    model_info = HYBRID_BERT_MODEL.get_info()
    print(f"[OK] Гибридная модель готова!")
    print(f"   Тип: {model_info['model_type']}")
    print(f"   Подход: {model_info['approach']}")
    print(f"   ML компонент: {'ДА' if model_info['ml_enabled'] else 'НЕТ'}")
    print(f"   BERT: {'ДА' if model_info['bert_loaded'] else 'НЕТ'}")
    print(f"   Classifier: {'ДА' if model_info['classifier_trained'] else 'НЕТ'}")
    
except Exception as e:
    print(f"[WARNING] Не удалось загрузить Гибридную модель: {e}")
    print(f"   Используется fallback regex подход")


def extract_text_from_pdf(pdf_bytes: bytes, verbose: bool = False) -> str:
    """
    Извлекает текст из PDF, используя PyMuPDF.
    Если PDF - скан или конвертированное изображение, автоматически использует Tesseract OCR.
    
    Args:
        pdf_bytes: Байты PDF файла
        verbose: Выводить подробные логи (по умолчанию False для скорости)
    """
    full_text = ""
    try:
        # Открываем PDF файл
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Обрабатываем каждую страницу
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()  # Пытаемся извлечь текст напрямую

            # Проверяем, нужен ли OCR
            text_stripped = text.strip()
            needs_ocr = (
                len(text_stripped) < 100 or  # Увеличили порог с 50 до 100
                text_stripped.replace('\n', '').replace(' ', '') == ''  # Только пробелы
            )
            
            if needs_ocr:
                if verbose:
                    print(f"[INFO] Страница {page_num + 1}: используется OCR (текста: {len(text_stripped)} символов)")
                
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                try:
                    # только русский язык
                    text = pytesseract.image_to_string(img, lang='rus', config='--psm 6 --oem 1')
                    if verbose:
                        print(f"[INFO] OCR извлёк {len(text.strip())} символов")
                except Exception as e:
                    if verbose:
                        print(f"[ERROR] Ошибка Tesseract на странице {page_num}: {e}")
                    text = ""
            else:
                if verbose:
                    print(f"[INFO] Страница {page_num + 1}: текст извлечён напрямую ({len(text_stripped)} символов)")

            full_text += text + "\n"

        doc.close()
        
        if len(full_text.strip()) == 0 and verbose:
            print("⚠️ Не удалось извлечь текст из PDF")
        
        return full_text

    except Exception as e:
        if verbose:
            print(f"[ERROR] Ошибка чтения PDF: {e}")
        return ""


def process_with_regex(raw_text: str) -> Dict[str, Any]:
    """
    Извлекает структурированные данные из текста чека с помощью регулярных выражений.
    Извлекаемые поля:
    - vendor: Наименование продавца/организации
    - inn: ИНН (10 или 12 цифр)
    - invoice_number: Номер документа/чека
    - date: Дата в различных форматах
    - total: Итоговая сумма
    - items: Список товаров (если обнаружены)
    """
    data = {}
    UNRECOGNIZED = "UNRECOGNIZED"  #для нераспознанных полей

    # 1. Извлечение ИНН (10 или 12 цифр)
    inn_match = re.search(r"ИНН[:\s]*(\d{10,12})", raw_text, re.IGNORECASE)
    if inn_match:
        data["inn"] = inn_match.group(1)
    else:
        data["inn"] = UNRECOGNIZED

    # 2. Извлечение названия организации (vendor)
    # Ищем перед ИНН или в начале
    vendor_patterns = [
        r"(ООО\s+[\"«]?[^\"»\n]+[\"»]?)",
        r"(АО\s+[\"«]?[^\"»\n]+[\"»]?)",
        r"(ИП\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)",
        r"([А-ЯЁ][А-ЯЁ\s]+(?:ООО|АО|ИП))",
    ]
    
    vendor_found = False
    for pattern in vendor_patterns:
        vendor_match = re.search(pattern, raw_text)
        if vendor_match:
            data["vendor"] = vendor_match.group(1).strip()
            vendor_found = True
            break
    
    if not vendor_found:
        data["vendor"] = UNRECOGNIZED

    # 3. Извлечение номера счета/чека
    invoice_patterns = [
        r"Счет[:\s-]*(?:фактура)?[:\s#№]*(\d+)",
        r"Чек[:\s#№]*(\d+)",
        r"Документ[:\s#№]*(\d+)",
        r"№[:\s]*(\d+)",
    ]
    
    invoice_found = False
    for pattern in invoice_patterns:
        invoice_match = re.search(pattern, raw_text, re.IGNORECASE)
        if invoice_match:
            data["invoice_number"] = invoice_match.group(1)
            invoice_found = True
            break
    
    if not invoice_found:
        data["invoice_number"] = UNRECOGNIZED

    # 4. Извлечение даты (различные форматы)
    date_patterns = [
        r"(\d{2}\.\d{2}\.\d{4})",  # 01.11.2025
        r"(\d{2}/\d{2}/\d{4})",    # 01/11/2025
        r"(\d{2}\.\d{2}\.\d{2})",  # 01.11.25
        r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})",  # 1 января 2025
        r"(\d{1,2}\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)\s+\d{4})",  # 1 янв 2025
    ]
    
    date_found = False
    for pattern in date_patterns:
        date_match = re.search(pattern, raw_text, re.IGNORECASE)
        if date_match:
            data["date"] = date_match.group(1)
            date_found = True
            break
    
    if not date_found:
        data["date"] = UNRECOGNIZED

    # 5. Извлечение итоговой суммы
    total_patterns = [
        r"(?:Итого|ИТОГО|Всего|ВСЕГО|К оплате|Сумма)[:\s=]*([\d\s]+[.,]\d{2})",
        r"(?:итог|total)[:\s=]*([\d\s]+[.,]\d{2})",
    ]
    
    total_found = False
    for pattern in total_patterns:
        total_match = re.search(pattern, raw_text, re.IGNORECASE)
        if total_match:
            amount_str = total_match.group(1).replace(" ", "").replace(",", ".")
            try:
                data["total"] = float(amount_str)
            except ValueError:
                data["total"] = amount_str
            total_found = True
            break
    
    if not total_found:
        data["total"] = UNRECOGNIZED

    # 6. Извлечение дополнительной информации
    # Телефон
    phone_match = re.search(r"[\+]?[7-8][\s-]?\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})", raw_text)
    if phone_match:
        data["phone"] = f"+7{phone_match.group(1)}{phone_match.group(2)}{phone_match.group(3)}{phone_match.group(4)}"

    # Email
    email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", raw_text)
    if email_match:
        data["email"] = email_match.group(1)

    # Адрес (базовая попытка)
    address_match = re.search(r"(?:Адрес|ADDRESS|адрес)[:\s]*([^\n]{10,100})", raw_text, re.IGNORECASE)
    if address_match:
        data["address"] = address_match.group(1).strip()

    return data


def extract_invoice_data(pdf_bytes: bytes, verbose: bool = False) -> Dict[str, Any]:
    """
    Главная функция-пайплайн для извлечения данных из PDF счета.
    
    Этапы обработки:
    1. Извлекает текст из PDF (с поддержкой OCR для сканов)
    2. Применяет обученную ML модель (если доступна) или regex-паттерны
    3. Форматирует и возвращает JSON с результатаме
    """
    try:
        # Шаг 1: Извлечение текста из PDF
        text = extract_text_from_pdf(pdf_bytes, verbose=verbose)
        
        if not text or len(text.strip()) < 10:
            return {
                "error": "Не удалось извлечь текст из PDF",
                "details": "PDF может быть пустым или поврежденным"
            }
        
        if verbose:
            print(f"[INFO] Извлечено {len(text)} символов текста")
        
        # Шаг 2: Обработка текста
        if HYBRID_BERT_MODEL is not None:
            # Используем Гибридную модель (ML + Regex)
            if verbose:
                print("[INFO] Используется Гибридная модель (ML + Regex)")
            extracted_data = HYBRID_BERT_MODEL.predict(text)
        else:
            # Fallback на regex подход
            if verbose:
                print("[INFO] Используется fallback regex подход")
            extracted_data = process_with_regex(text)
        
        # Убираем служебные поля (оставляем только данные)
        if 'ml_confidence' in extracted_data:
            del extracted_data['ml_confidence']
        
        return extracted_data
        
    except Exception as e:
        if verbose:
            print(f"[ERROR] Ошибка: {e}")
        return {
            "error": "Ошибка при обработке PDF",
            "details": str(e)
        }
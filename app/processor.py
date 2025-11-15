import fitz  # Чтение текста из ЦИФРОВЫХ PDF
import pytesseract  # OCR для сканированных PDF
from PIL import Image  # Помощь для tesseract
import io
import re  # Regular Expressions для извлечения данных
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Попытка загрузить обученную модель
TRAINED_MODEL = None

try:
    # Пробуем импорт для API (из корня проекта)
    try:
        from app.ml_model import InvoiceDataExtractor
        MODEL_PATH = Path("app/models/invoice_extractor.pkl")
    except ImportError:
        # Импорт для Jupyter ноутбуков (из app/)
        from ml_model import InvoiceDataExtractor
        MODEL_PATH = Path("models/invoice_extractor.pkl")
    
    if MODEL_PATH.exists():
        TRAINED_MODEL = InvoiceDataExtractor.load(str(MODEL_PATH))
        print(f"✅ Загружена обученная модель (точность: {TRAINED_MODEL.training_history['accuracy'][-1]:.2f}%)")
    else:
        print("⚠️ Обученная модель не найдена, используется regex подход")
except Exception as e:
    print(f"⚠️ Не удалось загрузить модель: {e}. Используется regex подход")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Извлекает текст из PDF, используя PyMuPDF.
    Если PDF - скан, автоматически использует Tesseract OCR.
    """
    full_text = ""
    try:
        # Открываем PDF файл
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Обрабатываем каждую страницу
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()  # Пытаемся извлечь текст напрямую

            # Если текста мало (скан), используем OCR
            if len(text.strip()) < 50:
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                try:
                    text = pytesseract.image_to_string(img, lang='rus+eng')
                except Exception as e:
                    print(f"Ошибка Tesseract на странице {page_num}: {e}")
                    text = ""

            full_text += text + "\n"

        doc.close()
        return full_text

    except Exception as e:
        print(f"Ошибка чтения PDF: {e}")
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
    
    Args:
        raw_text: Сырой текст, извлеченный из PDF
        
    Returns:
        Dict: Структурированные данные из чека
    """
    data = {}
    UNRECOGNIZED = "UNRECOGNIZED"  # Значение для нераспознанных полей

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


def extract_invoice_data(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Главная функция-пайплайн для извлечения данных из PDF счета.
    
    Этапы обработки:
    1. Извлекает текст из PDF (с поддержкой OCR для сканов)
    2. Применяет обученную ML модель (если доступна) или regex-паттерны
    3. Форматирует и возвращает JSON с результатами
    
    Args:
        pdf_bytes: Байты PDF файла
        
    Returns:
        Dict: Структурированные данные или сообщение об ошибке
    """
    try:
        # Шаг 1: Извлечение текста из PDF
        text = extract_text_from_pdf(pdf_bytes)
        
        if not text or len(text.strip()) < 10:
            return {
                "error": "Не удалось извлечь текст из PDF",
                "details": "PDF может быть пустым или поврежденным"
            }
        
        print(f"[INFO] Извлечено {len(text)} символов текста")
        
        # Шаг 2: Обработка текста
        if TRAINED_MODEL is not None:
            # Используем обученную ML модель
            print("[INFO] Используется обученная ML модель")
            extracted_data = TRAINED_MODEL.predict(text)
            extracted_data["method"] = "ml_model"
            extracted_data["model_accuracy"] = f"{TRAINED_MODEL.training_history['accuracy'][-1]:.2f}%"
        else:
            # Fallback на regex подход
            print("[INFO] Используется regex подход")
            extracted_data = process_with_regex(text)
            extracted_data["method"] = "regex"
        
        # Шаг 3: Добавление метаданных
        extracted_data["processing_status"] = "success"
        extracted_data["text_length"] = len(text)
        
        return extracted_data
        
    except Exception as e:
        return {
            "error": "Ошибка при обработке PDF",
            "details": str(e),
            "processing_status": "failed"
        }
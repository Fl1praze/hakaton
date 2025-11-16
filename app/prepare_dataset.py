"""простая подготовка данных для bert.
берем текст из pdf, jpeg, png и складываем в один json.
"""

import fitz  # чтение pdf
from pathlib import Path
import json
from PIL import Image
import pytesseract
import os


# быстрый поиск tesseract
if os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(pdf_path: str) -> str:
    """извлекает текст из pdf"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        
        for page_num, page in enumerate(doc):
            # обычный текст
            page_text = page.get_text()
            
            # скан и гоняем через ocr
            if len(page_text.strip()) < 50:
                print(f"         -> Страница {page_num+1}: используем OCR (мало текста)")
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img, lang='rus')
            
            text += page_text + "\n"
        
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"[ERROR] {pdf_path}: {e}")
        return ""


def extract_text_from_image(image_path: str) -> str:
    """извлекает текст из картинки через tesseract"""
    try:
        print(f"         -> Используем OCR для изображения")
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='rus', config='--psm 6 --oem 1')
        return text.strip()
    except Exception as e:
        print(f"[ERROR] {image_path}: {e}")
        return ""


def main():
    """обходит все файлы и собирает датасет"""
    print("="*80)
    print("ПОДГОТОВКА ДАТАСЕТА ДЛЯ BERT")
    print("="*80)
    
    # работаем от абсолютного пути к app
    script_dir = Path(__file__).parent.resolve()
    data_dir = script_dir / "pdf_for_study"
    output_file = script_dir / "dataset" / "raw_texts.json"
    
    # создаем папку для датасета если ее нет
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # немного логов чтобы видеть путь
    print(f"\n[INFO] Ищем файлы в: {data_dir.absolute()}")
    print(f"[INFO] Папка существует: {data_dir.exists()}")
    
    # собираем все поддерживаемые файлы
    pdf_files = list(data_dir.glob("*.pdf"))
    jpeg_files = list(data_dir.glob("*.jpg")) + list(data_dir.glob("*.jpeg"))
    png_files = list(data_dir.glob("*.png"))
    
    all_files = pdf_files + jpeg_files + png_files
    
    print(f"\n[OK] Найдено файлов:")
    print(f"     PDF:  {len(pdf_files)}")
    print(f"     JPEG: {len(jpeg_files)}")
    print(f"     PNG:  {len(png_files)}")
    print(f"     ВСЕГО: {len(all_files)}\n")
    
    dataset = []
    
    for i, file_path in enumerate(all_files, 1):
        file_ext = file_path.suffix.lower()
        print(f"[{i}/{len(all_files)}] Обработка: {file_path.name}")
        
        # выбираем способ вытаскивать текст
        if file_ext == '.pdf':
            text = extract_text_from_pdf(str(file_path))
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            text = extract_text_from_image(str(file_path))
        else:
            text = ""
        
        if text:
            dataset.append({
                "id": f"doc_{i}",
                "filename": file_path.name,
                "file_type": file_ext[1:],  # без точки
                "text": text,
                "length": len(text)
            })
            print(f"         -> Извлечено {len(text)} символов\n")
        else:
            print(f"         -> [SKIP] Пустой файл\n")
    
    # сохраняем датасет
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    print("="*80)
    print(f"[OK] ДАТАСЕТ СОЗДАН!")
    print("="*80)
    print(f"Документов: {len(dataset)}")
    print(f"Сохранено в: {output_file}")
    print(f"\nСтатистика по типам:")
    
    # считаем статистику по типам
    by_type = {}
    for doc in dataset:
        ftype = doc['file_type']
        by_type[ftype] = by_type.get(ftype, 0) + 1
    
    for ftype, count in by_type.items():
        print(f"  {ftype.upper()}: {count} документов")
    
    print(f"\nДетально:")
    for doc in dataset:
        print(f"  [{doc['file_type'].upper()}] {doc['filename'][:45]}: {doc['length']} символов")
    
    print(f"\n{'='*80}")
    print("СЛЕДУЮЩИЙ ШАГ: Загрузка и настройка BERT модели")
    print("="*80)
    print(f"[OK] Датасет готов ({len(dataset)} документов)")
    print(f"[OK] Тексты извлечены из PDF + JPEG + PNG")
    print(f"")
    print(f"Теперь запускаем обучение BERT!")
    print(f"  python app/train_bert.py")


if __name__ == "__main__":
    main()


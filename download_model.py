"""
Скрипт для загрузки обученной ML модели
Запускать перед первым стартом API, если model.pt отсутствует
"""

import os
import sys
from pathlib import Path
import urllib.request
from tqdm import tqdm

# Конфигурация
MODEL_DIR = Path("app/models/few_shot_classifier")
MODEL_FILE = MODEL_DIR / "model.pt"
MODEL_SIZE_MB = 678.53

# вариант 1: google drive (публичная ссылка)
# формат: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
GOOGLE_DRIVE_FILE_ID = "1JSfkUnS4Y0JlKzh7thPRoEMCIvruP7GE"

# вариант 2: прямая ссылка (если когда‑нибудь поменяешь хостинг)
DIRECT_URL = None  # например: "https://example.com/model.pt"


class DownloadProgressBar(tqdm):
    """Progress bar для urllib"""
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_from_google_drive(file_id: str, destination: Path):
    """Скачивает файл с Google Drive"""
    print(f"[INFO] Скачивание модели с Google Drive...")
    print(f"[INFO] File ID: {file_id}")
    
    # Google Drive direct download URL
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    try:
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=destination.name) as t:
            urllib.request.urlretrieve(url, destination, reporthook=t.update_to)
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке: {e}")
        return False


def download_from_direct_url(url: str, destination: Path):
    """Скачивает файл по прямой ссылке"""
    print(f"[INFO] Скачивание модели...")
    print(f"[INFO] URL: {url}")
    
    try:
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=destination.name) as t:
            urllib.request.urlretrieve(url, destination, reporthook=t.update_to)
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке: {e}")
        return False


def main():
    print("=" * 80)
    print("ЗАГРУЗКА ML МОДЕЛИ")
    print("=" * 80)
    print()
    
    # Проверяем существует ли модель
    if MODEL_FILE.exists():
        file_size_mb = MODEL_FILE.stat().st_size / 1024 / 1024
        print(f"[OK] Модель уже загружена: {MODEL_FILE}")
        print(f"[OK] Размер: {file_size_mb:.2f} MB")
        print()
        print("Если хотите перезагрузить модель, удалите файл и запустите скрипт снова.")
        return
    
    # Создаём директорию если не существует
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"[INFO] Модель не найдена: {MODEL_FILE}")
    print(f"[INFO] Ожидаемый размер: ~{MODEL_SIZE_MB:.2f} MB")
    print()
    
    # Выбираем метод загрузки
    if DIRECT_URL:
        print("[INFO] Используется прямая ссылка")
        success = download_from_direct_url(DIRECT_URL, MODEL_FILE)
    elif GOOGLE_DRIVE_FILE_ID != "YOUR_FILE_ID_HERE":
        print("[INFO] Используется Google Drive")
        success = download_from_google_drive(GOOGLE_DRIVE_FILE_ID, MODEL_FILE)
    else:
        print()
        print("=" * 80)
        print("ОШИБКА: НЕ НАСТРОЕНА ССЫЛКА НА МОДЕЛЬ!")
        print("=" * 80)
        print()
        print("Выберите один из вариантов:")
        print()
        print("ВАРИАНТ 1: Google Drive")
        print("  1. Загрузите model.pt на Google Drive")
        print("  2. Сделайте файл публично доступным")
        print("  3. Скопируйте FILE_ID из ссылки")
        print("  4. Вставьте в переменную GOOGLE_DRIVE_FILE_ID в этом скрипте")
        print()
        print("ВАРИАНТ 2: Прямая ссылка")
        print("  1. Загрузите model.pt на любое облачное хранилище")
        print("  2. Получите прямую ссылку для скачивания")
        print("  3. Вставьте в переменную DIRECT_URL в этом скрипте")
        print()
        print("ВАРИАНТ 3: Ручная загрузка")
        print("  1. Скопируйте model.pt вручную на сервер:")
        print(f"     scp model.pt user@server:{MODEL_FILE.absolute()}")
        print()
        sys.exit(1)
    
    # Проверяем результат
    if success and MODEL_FILE.exists():
        file_size_mb = MODEL_FILE.stat().st_size / 1024 / 1024
        print()
        print("=" * 80)
        print("[OK] МОДЕЛЬ УСПЕШНО ЗАГРУЖЕНА!")
        print("=" * 80)
        print(f"Файл: {MODEL_FILE}")
        print(f"Размер: {file_size_mb:.2f} MB")
        print()
        print("Теперь можно запускать API:")
        print("  uvicorn app.main:app --reload")
    else:
        print()
        print("=" * 80)
        print("[ERROR] НЕ УДАЛОСЬ ЗАГРУЗИТЬ МОДЕЛЬ!")
        print("=" * 80)
        print()
        print("Попробуйте скопировать model.pt вручную:")
        print(f"  scp model.pt user@server:{MODEL_FILE.absolute()}")


if __name__ == "__main__":
    main()



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
    
    # если файл не найден — показываем понятную инструкцию и выходим
    print(f"[INFO] Модель не найдена: {MODEL_FILE}")
    print(f"[INFO] Ожидаемый размер: ~{MODEL_SIZE_MB:.2f} MB")
    print()
    print("=" * 80)
    print("МОДЕЛЬ НЕ СКАЧАНА")
    print("=" * 80)
    print()
    print("Скачайте файл model.pt вручную по ссылке:")
    print("  https://drive.google.com/file/d/1JSfkUnS4Y0JlKzh7thPRoEMCIvruP7GE/view")
    print()
    print("И сохраните его в папку:")
    print(f"  {MODEL_FILE}")
    print()
    print("После этого снова запустите:")
    print("  python download_model.py")
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()



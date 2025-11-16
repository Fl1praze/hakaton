from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, List
from app import processor
import logging
import io
from PIL import Image
import tempfile
import os

# простая настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K-Telecom PDF Parser API",
    description="API для извлечения структурированных данных из PDF-счетов",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """простой ping эндпоинт."""
    return {
        "message": "API для обработки PDF-счетов работает",
        "version": "1.0.0",
        "endpoints": {
            "process_pdf": "/api/process_pdf/",
            "process_batch": "/api/process-batch/",
            "convert_to_pdf": "/api/convert-to-pdf/",
            "documentation": "/docs",
            "health": "/health"
        }
    }


@app.get("/health", tags=["System"])
def health_check():
    """минимальная проверка здоровья сервиса."""
    return {
        "status": "healthy",
        "service": "pdf-parser-api"
    }


@app.post("/api/process_pdf/", tags=["PDF Processing"], status_code=status.HTTP_200_OK)
async def process_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """принимает один pdf и возвращает распарсенный json."""
    try:
        # читаем весь файл в память
        pdf_bytes = await file.read()
        
        # быстрые валидации
        if len(pdf_bytes) == 0:
            logger.warning("Получен пустой файл")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Файл пуст"
            )
        
        # проверяем magic bytes: pdf всегда начинается с %pdf-
        if not pdf_bytes.startswith(b'%PDF-'):
            logger.warning(f"Файл {file.filename} не является PDF (magic bytes проверка)")
            logger.warning(f"Первые байты: {pdf_bytes[:20]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Файл не является PDF документом"
            )
        
        if len(pdf_bytes) > 10 * 1024 * 1024:  # лимит 10 мб
            logger.warning(f"Файл слишком большой: {len(pdf_bytes)} байт")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Размер файла превышает 10 МБ"
            )
        
        logger.info(f"Обработка файла: {file.filename}, размер: {len(pdf_bytes)} байт")
        
        # запускаем основной парсер
        extracted_data = processor.extract_invoice_data(pdf_bytes, verbose=False)
        
        # смотрим нет ли ошибки
        if "error" in extracted_data:
            logger.error(f"Ошибка обработки: {extracted_data.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось обработать файл: {extracted_data.get('error', 'Неизвестная ошибка')}"
            )
        
        # успешный ответ
        logger.info(f"Файл {file.filename} успешно обработан")
        return {
            "status": "success",
            "filename": file.filename,
            "data": extracted_data
        }
        
    except HTTPException:
        # http ошибки пробрасываем как есть
        raise
        
    except Exception as e:
        # все остальное считаем 500
        logger.error(f"Непредвиденная ошибка: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Попробуйте позже"
        )


@app.post("/api/process-batch/", tags=["PDF Processing"], status_code=status.HTTP_200_OK)
async def process_pdf_batch(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """
    Принимает несколько PDF-файлов, обрабатывает их и возвращает результаты для каждого.
    Возвращает:
    - total: общее количество файлов
    - successful: количество успешно обработанных
    - failed: количество файлов с ошибками
    - results: список результатов для каждого файла
    """
    logger.info(f"Получено {len(files)} файлов для batch обработки")
    
    results = []
    successful = 0
    failed = 0
    
    # ПАРАЛЛЕЛЬНАЯ обработка файлов
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    async def process_one_file(file: UploadFile) -> Dict[str, Any]:
        """Обработка одного файла"""
        try:
            pdf_bytes = await file.read()
            
            if len(pdf_bytes) == 0:
                return {
                    "filename": file.filename,
                    "status": "error",
                    "error": "Файл пуст"
                }
            
            if not pdf_bytes.startswith(b'%PDF-'):
                return {
                    "filename": file.filename,
                    "status": "error",
                    "error": "Файл не является PDF документом"
                }
            
            if len(pdf_bytes) > 10 * 1024 * 1024:
                return {
                    "filename": file.filename,
                    "status": "error",
                    "error": "Размер файла превышает 10 МБ"
                }
            
            logger.info(f"Обработка файла: {file.filename}, размер: {len(pdf_bytes)} байт")
            
            # Обработка в отдельном потоке для параллелизма
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                extracted_data = await loop.run_in_executor(
                    pool,
                    processor.extract_invoice_data,
                    pdf_bytes,
                    False
                )
            
            if "error" in extracted_data:
                return {
                    "filename": file.filename,
                    "status": "error",
                    "error": extracted_data.get("error", "Неизвестная ошибка")
                }
            else:
                return {
                    "filename": file.filename,
                    "status": "success",
                    "data": extracted_data
                }
                
        except Exception as e:
            logger.error(f"Ошибка при обработке {file.filename}: {str(e)}")
            return {
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            }
    
    # Обрабатываем ВСЕ файлы параллельно
    results = await asyncio.gather(*[process_one_file(f) for f in files])
    
    # Подсчет статистики
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "error")
    
    logger.info(f"Batch обработка завершена: {successful} успешно, {failed} с ошибками")
    
    return {
        "status": "completed",
        "total": len(files),
        "successful": successful,
        "failed": failed,
        "results": results
    }

# Обработчик глобальных исключений
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Глобальная ошибка: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"}
    )
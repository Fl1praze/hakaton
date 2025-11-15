from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
from app import processor
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K-Telecom PDF Parser API",
    description="API для извлечения структурированных данных из PDF-счетов",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS для Go бота
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """
    Корневой эндпоинт - проверка работоспособности API
    """
    return {
        "message": "API для обработки PDF-счетов работает",
        "version": "1.0.0",
        "endpoints": {
            "process_pdf": "/api/process_pdf/",
            "process_batch": "/api/process-batch/",
            "documentation": "/docs",
            "health": "/health"
        }
    }


@app.get("/health", tags=["System"])
def health_check():
    """
    Проверка здоровья сервиса
    """
    return {
        "status": "healthy",
        "service": "pdf-parser-api"
    }


@app.post("/api/process_pdf/", tags=["PDF Processing"], status_code=status.HTTP_200_OK)
async def process_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Принимает PDF-файл, извлекает структурированные данные и возвращает JSON.
    """
    try:
        # Проверка типа файла
        if not file.filename.lower().endswith('.pdf'):
            logger.warning(f"Неверный формат файла: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Загрузите файл в формате PDF"
            )
        
        # Проверка content-type (может быть None)
        if file.content_type and file.content_type != "application/pdf":
            logger.warning(f"Неверный content-type: {file.content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Неверный тип файла. Требуется PDF"
            )
        
        # Читаем файл
        pdf_bytes = await file.read()
        
        # Проверка размера файла
        if len(pdf_bytes) == 0:
            logger.warning("Получен пустой файл")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Файл пуст"
            )
        
        if len(pdf_bytes) > 10 * 1024 * 1024:  # 10 MB лимит
            logger.warning(f"Файл слишком большой: {len(pdf_bytes)} байт")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка: Размер файла превышает 10 МБ"
            )
        
        logger.info(f"Обработка файла: {file.filename}, размер: {len(pdf_bytes)} байт")
        
        # Вызываем функцию обработки
        extracted_data = processor.extract_invoice_data(pdf_bytes)
        
        # Проверка на ошибки обработки
        if "error" in extracted_data:
            logger.error(f"Ошибка обработки: {extracted_data.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось обработать файл: {extracted_data.get('error', 'Неизвестная ошибка')}"
            )
        
        # Успешный результат
        logger.info(f"Файл {file.filename} успешно обработан")
        return {
            "status": "success",
            "filename": file.filename,
            "data": extracted_data
        }
        
    except HTTPException:
        # Пробрасываем HTTP исключения дальше
        raise
        
    except Exception as e:
        # Любые другие непредвиденные ошибки
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
    
    for file in files:
        try:
            # Проверка типа файла
            if not file.filename.lower().endswith('.pdf'):
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": "Неверный формат файла. Требуется PDF"
                })
                failed += 1
                continue
            
            # Читаем файл
            pdf_bytes = await file.read()
            
            # Проверка размера
            if len(pdf_bytes) == 0:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": "Файл пуст"
                })
                failed += 1
                continue
            
            if len(pdf_bytes) > 10 * 1024 * 1024:  # 10 MB лимит
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": "Размер файла превышает 10 МБ"
                })
                failed += 1
                continue
            
            logger.info(f"Обработка файла: {file.filename}, размер: {len(pdf_bytes)} байт")
            
            # Обработка
            extracted_data = processor.extract_invoice_data(pdf_bytes)
            
            if "error" in extracted_data:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": extracted_data.get("error", "Неизвестная ошибка")
                })
                failed += 1
            else:
                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "data": extracted_data
                })
                successful += 1
                
        except Exception as e:
            logger.error(f"Ошибка при обработке {file.filename}: {str(e)}")
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
            failed += 1
    
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
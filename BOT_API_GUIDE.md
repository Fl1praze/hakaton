# 🤖 API Guide для Go Бота

Полная документация по интеграции Telegram/Discord бота с API для обработки PDF чеков.

---

## 📡 Базовая Информация

- **Base URL:** `http://localhost:8000` (в продакшене замените на ваш домен)
- **Формат данных:** JSON
- **Метод:** POST (multipart/form-data)
- **Максимальный размер файла:** 10 МБ
- **Поддерживаемые форматы:** PDF

---

## 🔥 Эндпоинты

### 1. `/api/process_pdf/` - Обработка 1 файла

**Описание:** Отправляете 1 PDF файл → получаете извлечённые данные.

**Использование:**

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

// ProcessSinglePDF отправляет 1 PDF файл на обработку
func ProcessSinglePDF(filePath string) (map[string]interface{}, error) {
    // Открываем файл
    file, err := os.Open(filePath)
    if err != nil {
        return nil, fmt.Errorf("ошибка открытия файла: %w", err)
    }
    defer file.Close()

    // Создаём multipart form
    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)
    
    // Добавляем файл
    part, err := writer.CreateFormFile("file", filePath)
    if err != nil {
        return nil, fmt.Errorf("ошибка создания form file: %w", err)
    }
    
    _, err = io.Copy(part, file)
    if err != nil {
        return nil, fmt.Errorf("ошибка копирования файла: %w", err)
    }
    
    writer.Close()

    // Отправляем запрос
    req, err := http.NewRequest("POST", "http://localhost:8000/api/process_pdf/", body)
    if err != nil {
        return nil, fmt.Errorf("ошибка создания запроса: %w", err)
    }
    
    req.Header.Set("Content-Type", writer.FormDataContentType())

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("ошибка отправки запроса: %w", err)
    }
    defer resp.Body.Close()

    // Читаем ответ
    var result map[string]interface{}
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("ошибка парсинга ответа: %w", err)
    }

    // Проверяем статус
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("API вернул ошибку: %v", result)
    }

    return result, nil
}

func main() {
    result, err := ProcessSinglePDF("invoice.pdf")
    if err != nil {
        fmt.Printf("Ошибка: %v\n", err)
        return
    }
    
    fmt.Printf("Результат: %+v\n", result)
}
```

**Пример ответа:**

```json
{
  "status": "success",
  "filename": "invoice.pdf",
  "data": {
    "inn": "7707083893",
    "vendor": "ООО РОГА И КОПЫТА",
    "invoice_number": "INV-2024-001",
    "date": "2024-11-15",
    "total": "5432.10",
    "phone": "+7 (495) 123-45-67",
    "email": "info@company.ru",
    "address": "Москва, ул. Ленина 1",
    "method": "ml_model",
    "model_accuracy": "92.50%"
  }
}
```

---

### 2. `/api/process-batch/` - Обработка нескольких файлов

**Описание:** Отправляете несколько PDF файлов → получаете результаты для каждого.

**Использование:**

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

// ProcessBatchPDFs отправляет несколько PDF файлов на обработку
func ProcessBatchPDFs(filePaths []string) (map[string]interface{}, error) {
    // Создаём multipart form
    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)
    
    // Добавляем все файлы
    for _, filePath := range filePaths {
        file, err := os.Open(filePath)
        if err != nil {
            return nil, fmt.Errorf("ошибка открытия %s: %w", filePath, err)
        }
        
        part, err := writer.CreateFormFile("files", filePath)
        if err != nil {
            file.Close()
            return nil, fmt.Errorf("ошибка создания form file: %w", err)
        }
        
        _, err = io.Copy(part, file)
        file.Close()
        
        if err != nil {
            return nil, fmt.Errorf("ошибка копирования файла: %w", err)
        }
    }
    
    writer.Close()

    // Отправляем запрос
    req, err := http.NewRequest("POST", "http://localhost:8000/api/process-batch/", body)
    if err != nil {
        return nil, fmt.Errorf("ошибка создания запроса: %w", err)
    }
    
    req.Header.Set("Content-Type", writer.FormDataContentType())

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, fmt.Errorf("ошибка отправки запроса: %w", err)
    }
    defer resp.Body.Close()

    // Читаем ответ
    var result map[string]interface{}
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("ошибка парсинга ответа: %w", err)
    }

    return result, nil
}

func main() {
    files := []string{"invoice1.pdf", "invoice2.pdf", "invoice3.pdf"}
    
    result, err := ProcessBatchPDFs(files)
    if err != nil {
        fmt.Printf("Ошибка: %v\n", err)
        return
    }
    
    fmt.Printf("Результат batch обработки: %+v\n", result)
}
```

**Пример ответа:**

```json
{
  "status": "completed",
  "total": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "filename": "invoice1.pdf",
      "status": "success",
      "data": {
        "inn": "7707083893",
        "vendor": "ООО МАГАЗИН",
        "date": "2024-11-15",
        "total": "1234.56",
        "method": "ml_model"
      }
    },
    {
      "filename": "invoice2.pdf",
      "status": "success",
      "data": {
        "inn": "5004002123",
        "vendor": "ИП Иванов",
        "date": "2024-11-14",
        "total": "999.00",
        "method": "regex"
      }
    },
    {
      "filename": "invoice3.pdf",
      "status": "error",
      "error": "Не удалось извлечь текст из PDF"
    }
  ]
}
```

---

## 🎯 Интеграция с Telegram Bot

### Пример обработки документов от пользователя

```go
package main

import (
    "fmt"
    tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
    "io"
    "net/http"
    "os"
)

func handleDocument(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
    // Получаем информацию о файле
    fileID := update.Message.Document.FileID
    file, err := bot.GetFile(tgbotapi.FileConfig{FileID: fileID})
    if err != nil {
        bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Ошибка получения файла"))
        return
    }

    // Скачиваем файл
    fileURL := file.Link(bot.Token)
    resp, err := http.Get(fileURL)
    if err != nil {
        bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Ошибка скачивания файла"))
        return
    }
    defer resp.Body.Close()

    // Сохраняем временно
    tempFile, err := os.CreateTemp("", "invoice-*.pdf")
    if err != nil {
        bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Ошибка создания временного файла"))
        return
    }
    defer os.Remove(tempFile.Name())

    _, err = io.Copy(tempFile, resp.Body)
    tempFile.Close()
    if err != nil {
        bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Ошибка сохранения файла"))
        return
    }

    // Отправляем на обработку
    bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, "⏳ Обрабатываю PDF..."))
    
    result, err := ProcessSinglePDF(tempFile.Name())
    if err != nil {
        bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, 
            fmt.Sprintf("❌ Ошибка обработки: %v", err)))
        return
    }

    // Форматируем результат
    data := result["data"].(map[string]interface{})
    message := fmt.Sprintf(`✅ Данные извлечены:

📋 ИНН: %v
🏢 Поставщик: %v
📅 Дата: %v
💰 Сумма: %v руб.
📞 Телефон: %v
📧 Email: %v
📍 Адрес: %v

🤖 Метод: %v`,
        data["inn"],
        data["vendor"],
        data["date"],
        data["total"],
        data["phone"],
        data["email"],
        data["address"],
        data["method"])

    bot.Send(tgbotapi.NewMessage(update.Message.Chat.ID, message))
}
```

---

## ⚠️ Обработка Ошибок

### Типы ошибок

| HTTP Код | Описание | Решение |
|----------|----------|---------|
| `400` | Неверный формат/размер файла | Проверьте, что файл в формате PDF и < 10 МБ |
| `500` | Ошибка обработки | Попробуйте другой файл или свяжитесь с поддержкой |

### Пример обработки в Go

```go
if resp.StatusCode == http.StatusBadRequest {
    // Неверный формат файла
    bot.Send(tgbotapi.NewMessage(chatID, 
        "❌ Пожалуйста, отправьте файл в формате PDF (до 10 МБ)"))
} else if resp.StatusCode == http.StatusInternalServerError {
    // Ошибка сервера
    bot.Send(tgbotapi.NewMessage(chatID, 
        "❌ Не удалось обработать файл. Попробуйте другой PDF или позже."))
}
```

---

## 🔍 Проверка API

### Проверка здоровья

```bash
curl http://localhost:8000/health
```

**Ответ:**
```json
{
  "status": "healthy",
  "service": "pdf-parser-api"
}
```

### Тест через curl (1 файл)

```bash
curl -X POST http://localhost:8000/api/process_pdf/ \
  -F "file=@invoice.pdf"
```

### Тест через curl (несколько файлов)

```bash
curl -X POST http://localhost:8000/api/process-batch/ \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@invoice3.pdf"
```

---

## 📊 Swagger Документация

После запуска API, откройте в браузере:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Там вы сможете:
- Увидеть все эндпоинты
- Протестировать API прямо в браузере
- Посмотреть примеры запросов/ответов

---

## 🚀 Запуск API

```bash
# С Docker (рекомендуется)
docker-compose up -d

# Или без Docker
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 💡 Советы

1. **Batch vs Single:**
   - Используйте `/api/process-batch/` если пользователь загрузил несколько файлов
   - Используйте `/api/process_pdf/` для 1 файла (быстрее)

2. **Timeout:**
   - Установите timeout 30-60 секунд для HTTP клиента
   - OCR может занимать время на больших PDF

3. **Retry Logic:**
   - Если получили 500 ошибку, попробуйте ещё 1-2 раза
   - Для batch обработки: обрабатывайте успешные результаты даже если часть файлов упала

4. **Валидация:**
   - Проверяйте расширение файла ДО отправки на API
   - Проверяйте размер файла (< 10 МБ)

---

## 📞 Поддержка

Если возникли вопросы:
- Проверьте логи API: `docker-compose logs -f api`
- Откройте Swagger: http://localhost:8000/docs
- Проверьте health check: http://localhost:8000/health

---

**Версия API:** 1.0.0  
**Дата обновления:** 15.11.2024


package services

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/hakaton/pdf-bot/internal/clients"
)

type PDFService struct {
	apiClient     *clients.APIClient
	maxFileSizeMB int64
}

func NewPDFService(apiClient *clients.APIClient, maxFileSizeMB int64) *PDFService {
	return &PDFService{
		apiClient:     apiClient,
		maxFileSizeMB: maxFileSizeMB,
	}
}

// escapeHTML экранирует html для безопасного вывода в telegram
func escapeHTML(text string) string {
	text = strings.ReplaceAll(text, "&", "&amp;")
	text = strings.ReplaceAll(text, "<", "&lt;")
	text = strings.ReplaceAll(text, ">", "&gt;")
	return text
}

func (s *PDFService) ProcessPDFFromURL(fileURL, filename string) (string, error) {
	log.Printf("[PDF Service] Скачивание файла: %s", filename)

	resp, err := http.Get(fileURL)
	if err != nil {
		return "", fmt.Errorf("не удалось скачать файл: %w", err)
	}
	defer resp.Body.Close()

	fileBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("не удалось прочитать файл: %w", err)
	}

	fileSizeMB := int64(len(fileBytes)) / (1024 * 1024)
	if fileSizeMB > s.maxFileSizeMB {
		return "", fmt.Errorf("файл слишком большой: %d МБ (максимум: %d МБ)", fileSizeMB, s.maxFileSizeMB)
	}

	log.Printf("[PDF Service] Файл скачан: %d байт", len(fileBytes))

	result, err := s.apiClient.ProcessPDF(fileBytes, filename)
	if err != nil {
		return "", fmt.Errorf("ошибка обработки PDF: %w", err)
	}

	return s.formatResult(result), nil
}

// ProcessMultiplePDFsFromURLs обрабатывает несколько pdf по ссылкам
func (s *PDFService) ProcessMultiplePDFsFromURLs(fileURLs []string, filenames []string) (string, error) {
	if len(fileURLs) != len(filenames) {
		return "", fmt.Errorf("количество URL и имен файлов не совпадает")
	}

	log.Printf("[PDF Service] Пакетная обработка: %d файлов", len(fileURLs))

	// скачиваем все файлы
	var files [][]byte
	for i, fileURL := range fileURLs {
		log.Printf("[PDF Service] Скачивание файла %d/%d: %s", i+1, len(fileURLs), filenames[i])

		resp, err := http.Get(fileURL)
		if err != nil {
			return "", fmt.Errorf("не удалось скачать файл %s: %w", filenames[i], err)
		}
		defer resp.Body.Close()

		fileBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return "", fmt.Errorf("не удалось прочитать файл %s: %w", filenames[i], err)
		}

		fileSizeMB := int64(len(fileBytes)) / (1024 * 1024)
		if fileSizeMB > s.maxFileSizeMB {
			return "", fmt.Errorf("файл %s слишком большой: %d МБ (максимум: %d МБ)", filenames[i], fileSizeMB, s.maxFileSizeMB)
		}

		files = append(files, fileBytes)
		log.Printf("[PDF Service] Файл %s скачан: %d байт", filenames[i], len(fileBytes))
	}

	// отправляем в api на обработку
	result, err := s.apiClient.ProcessBatch(files, filenames)
	if err != nil {
		return "", fmt.Errorf("ошибка пакетной обработки: %w", err)
	}

	return s.formatBatchResult(result), nil
}

func (s *PDFService) formatBatchResult(result *clients.BatchProcessResponse) string {
	message := "✅ <b>Пакетная обработка завершена!</b>\n\n"
	
	// Статистика
	if summary := result.Summary; summary != nil {
		if total, ok := summary["total_files"].(float64); ok {
			message += fmt.Sprintf("📊 <b>Обработано файлов:</b> %.0f\n", total)
		}
		if success, ok := summary["successful"].(float64); ok {
			message += fmt.Sprintf("✅ <b>Успешно:</b> %.0f\n", success)
		}
		if failed, ok := summary["failed"].(float64); ok && failed > 0 {
			message += fmt.Sprintf("❌ <b>С ошибками:</b> %.0f\n", failed)
		}
	}
	message += "\n"

	// Результаты для каждого файла
	for i, fileResult := range result.Results {
		message += fmt.Sprintf("━━━━━━━━━━━━━━━━━━\n")
		message += fmt.Sprintf("📄 <b>Файл %d: %s</b>\n\n", i+1, escapeHTML(fileResult.Filename))
		
		if fileResult.Status == "success" {
			// Основные данные
			message += s.formatSingleFileData(fileResult.Data)
			
			// RAW JSON для каждого файла
			message += "\n━━━━━━━━━━━━━━━━━━\n"
			message += "📄 <b>JSON ответ:</b>\n"
			message += "<pre>"
			
			jsonBytes, err := json.MarshalIndent(fileResult.Data, "", "  ")
			if err == nil {
				jsonStr := string(jsonBytes)
				// Обрезаем если слишком длинный (для множества файлов)
				if len(jsonStr) > 1500 {
					jsonStr = jsonStr[:1500] + "\n... (обрезано)"
				}
				message += escapeHTML(jsonStr)
			}
			message += "</pre>\n"
		} else {
			message += "❌ <i>Ошибка обработки</i>\n"
		}
		message += "\n"
	}

	return message
}

func (s *PDFService) formatSingleFileData(data map[string]interface{}) string {
	message := ""

	// Функция для извлечения значения (массив или строка)
	getValue := func(key string) string {
		if val, ok := data[key]; ok {
			// Если массив - берем первый элемент
			if arr, ok := val.([]interface{}); ok && len(arr) > 0 {
				if str, ok := arr[0].(string); ok {
					return str
				}
			}
			// Если строка - возвращаем как есть
			if str, ok := val.(string); ok {
				return str
			}
		}
		return ""
	}

	// Собираем основные поля для проверки дубликатов
	shownValues := make(map[string]bool)
	
	// === ОСНОВНАЯ ИНФОРМАЦИЯ ===
	message += "<b>🧾 ОСНОВНАЯ ИНФОРМАЦИЯ:</b>\n"
	
	if inn := getValue("inn"); inn != "" && inn != "UNRECOGNIZED" {
		message += fmt.Sprintf("  📋 <b>ИНН:</b> <code>%s</code>\n", escapeHTML(inn))
		shownValues[inn] = true
	}

	if vendor := getValue("vendor"); vendor != "" && vendor != "UNRECOGNIZED" {
		// Обрезаем vendor если слишком длинный
		vendorStr := vendor
		if len(vendorStr) > 80 {
			vendorStr = vendorStr[:80] + "..."
		}
		message += fmt.Sprintf("  🏢 <b>Поставщик:</b> %s\n", escapeHTML(vendorStr))
		shownValues[vendor] = true
	}
	
	if date := getValue("date"); date != "" && date != "UNRECOGNIZED" {
		message += fmt.Sprintf("  📅 <b>Дата:</b> %s\n", escapeHTML(date))
		shownValues[date] = true
	}
	
	if time := getValue("time"); time != "" && time != "UNRECOGNIZED" {
		message += fmt.Sprintf("  🕐 <b>Время:</b> %s\n", escapeHTML(time))
		shownValues[time] = true
	}
	
	// ИТОГО / Сумма (ВАЖНО!)
	if total := getValue("total"); total != "" && total != "UNRECOGNIZED" {
		message += fmt.Sprintf("  💰 <b>ИТОГО:</b> <code>%s руб.</code>\n", escapeHTML(total))
		shownValues[total] = true
	}

	// === КОНТАКТЫ ===
	hasContacts := false
	contactsMsg := "\n<b>📞 КОНТАКТЫ:</b>\n"
	
	if phone := getValue("phone"); phone != "" && phone != "UNRECOGNIZED" {
		contactsMsg += fmt.Sprintf("  📞 <b>Телефон:</b> %s\n", escapeHTML(phone))
		shownValues[phone] = true
		hasContacts = true
	}

	if email := getValue("email"); email != "" && email != "UNRECOGNIZED" {
		contactsMsg += fmt.Sprintf("  📧 <b>Email:</b> %s\n", escapeHTML(email))
		shownValues[email] = true
		hasContacts = true
	}
	
	if hasContacts {
		message += contactsMsg
	}

	// === ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ (auto_extracted) ===
	if autoExtracted, ok := data["auto_extracted"].(map[string]interface{}); ok && len(autoExtracted) > 0 {
		// Фильтруем дубликаты и группируем
		filteredData := make(map[string]string)
		
		for key, value := range autoExtracted {
			if value == nil || value == "" || value == "UNRECOGNIZED" {
				continue
			}
			
			valueStr := fmt.Sprintf("%v", value)
			
			// Пропускаем если значение уже показано выше
			if shownValues[valueStr] {
				continue
			}
			
			// Пропускаем слишком длинные значения (вероятно мусор)
			if len(valueStr) > 100 {
				continue
			}
			
			// Пропускаем если слишком много слов (предложения, а не данные)
			words := len(strings.Fields(valueStr))
			if words > 10 {
				continue
			}
			
			filteredData[key] = valueStr
		}
		
		if len(filteredData) > 0 {
			message += "\n<b>📦 ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ:</b>\n"
			for key, value := range filteredData {
				message += fmt.Sprintf("  • <i>%s:</i> %s\n", escapeHTML(key), escapeHTML(value))
			}
		}
	}

	return message
}

func (s *PDFService) formatResult(result *clients.ProcessPDFResponse) string {
	data := result.Data

	message := "✅ <b>Данные успешно извлечены из чека!</b>\n\n"
	message += s.formatSingleFileData(data)

	// Добавляем RAW JSON (требование ТЗ!)
	message += "\n━━━━━━━━━━━━━━━━━━\n"
	message += "📄 <b>JSON ответ от API:</b>\n"
	message += "<pre>"
	
	// Форматируем JSON
	jsonBytes, err := json.MarshalIndent(data, "", "  ")
	if err == nil {
		jsonStr := string(jsonBytes)
		// Обрезаем если слишком длинный (лимит Telegram ~4096 символов)
		if len(jsonStr) > 2000 {
			jsonStr = jsonStr[:2000] + "\n... (обрезано)"
		}
		message += escapeHTML(jsonStr)
	}
	message += "</pre>"

	return message
}

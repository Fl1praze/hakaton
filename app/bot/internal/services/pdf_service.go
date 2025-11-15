package services

import (
	"fmt"
	"io"
	"log"
	"net/http"

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

func (s *PDFService) formatResult(result *clients.ProcessPDFResponse) string {
	data := result.Data

	message := "✅ <b>Данные успешно извлечены из чека!</b>\n\n"

	if inn, ok := data["inn"].(string); ok && inn != "UNRECOGNIZED" {
		message += fmt.Sprintf("📋 <b>ИНН:</b> <code>%s</code>\n", inn)
	}

	if vendor, ok := data["vendor"].(string); ok && vendor != "UNRECOGNIZED" {
		message += fmt.Sprintf("🏢 <b>Поставщик:</b> %s\n", vendor)
	}

	if invoiceNum, ok := data["invoice_number"].(string); ok && invoiceNum != "UNRECOGNIZED" {
		message += fmt.Sprintf("📄 <b>Номер документа:</b> %s\n", invoiceNum)
	}

	if date, ok := data["date"].(string); ok && date != "UNRECOGNIZED" {
		message += fmt.Sprintf("📅 <b>Дата:</b> %s\n", date)
	}

	if total := data["total"]; total != nil && total != "UNRECOGNIZED" {
		message += fmt.Sprintf("💰 <b>Сумма:</b> %v руб.\n", total)
	}

	if phone, ok := data["phone"].(string); ok {
		message += fmt.Sprintf("📞 <b>Телефон:</b> %s\n", phone)
	}

	if email, ok := data["email"].(string); ok {
		message += fmt.Sprintf("📧 <b>Email:</b> %s\n", email)
	}

	if address, ok := data["address"].(string); ok {
		message += fmt.Sprintf("📍 <b>Адрес:</b> %s\n", address)
	}

	message += "\n"
	if method, ok := data["method"].(string); ok {
		methodIcon := "🤖"
		if method == "regex" {
			methodIcon = "🔍"
		}
		message += fmt.Sprintf("%s <i>Метод: %s</i>\n", methodIcon, method)
	}

	if accuracy, ok := data["model_accuracy"].(string); ok {
		message += fmt.Sprintf("📊 <i>Точность модели: %s</i>\n", accuracy)
	}

	return message
}

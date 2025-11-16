package clients

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"time"
)

type APIClient struct {
	baseURL    string
	httpClient *http.Client
}

type ProcessPDFResponse struct {
	Status   string                 `json:"status"`
	Filename string                 `json:"filename"`
	Data     map[string]interface{} `json:"data"`
}

type BatchProcessResponse struct {
	Status  string                   `json:"status"`
	Message string                   `json:"message"`
	Results []ProcessPDFResponse     `json:"results"`
	Summary map[string]interface{}   `json:"summary"`
}

type ErrorResponse struct {
	Detail string `json:"detail"`
}

func NewAPIClient(baseURL string) *APIClient {
	return &APIClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 90 * time.Second, // Увеличено для пакетной обработки
		},
	}
}

// ProcessPDF отправляет PDF файл на обработку в backend API
func (c *APIClient) ProcessPDF(fileBytes []byte, filename string) (*ProcessPDFResponse, error) {
	log.Printf("[API] Отправка файла %s на обработку (размер: %d байт)", filename, len(fileBytes))

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("file", filename)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания form file: %w", err)
	}

	_, err = part.Write(fileBytes)
	if err != nil {
		return nil, fmt.Errorf("ошибка записи файла: %w", err)
	}

	err = writer.Close()
	if err != nil {
		return nil, fmt.Errorf("ошибка закрытия writer: %w", err)
	}

	url := fmt.Sprintf("%s/api/process_pdf/", c.baseURL)
	req, err := http.NewRequest("POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса: %w", err)
	}

	req.Header.Set("Content-Type", writer.FormDataContentType())

	log.Printf("[API] POST %s", url)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка отправки запроса: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	log.Printf("[API] Получен ответ: статус %d", resp.StatusCode)

	if resp.StatusCode != http.StatusOK {
		var errResp ErrorResponse
		if err := json.Unmarshal(respBody, &errResp); err == nil && errResp.Detail != "" {
			return nil, fmt.Errorf("ошибка API: %s", errResp.Detail)
		}
		return nil, fmt.Errorf("ошибка API: статус %d", resp.StatusCode)
	}

	var result ProcessPDFResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("ошибка парсинга ответа: %w", err)
	}

	// Подсчитываем сколько полей найдено
	fieldCount := 0
	for key, value := range result.Data {
		if key != "auto_extracted" && value != nil && value != "" {
			fieldCount++
		}
	}
	log.Printf("[API] Файл успешно обработан, найдено полей: %d", fieldCount)
	return &result, nil
}

// ProcessBatch отправляет несколько PDF файлов на обработку в backend API
func (c *APIClient) ProcessBatch(files [][]byte, filenames []string) (*BatchProcessResponse, error) {
	if len(files) != len(filenames) {
		return nil, fmt.Errorf("количество файлов и имен не совпадает")
	}

	log.Printf("[API] Отправка %d файлов на пакетную обработку", len(files))

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// Добавляем все файлы
	for i, fileBytes := range files {
		part, err := writer.CreateFormFile("files", filenames[i])
		if err != nil {
			return nil, fmt.Errorf("ошибка создания form file для %s: %w", filenames[i], err)
		}

		_, err = part.Write(fileBytes)
		if err != nil {
			return nil, fmt.Errorf("ошибка записи файла %s: %w", filenames[i], err)
		}
		log.Printf("[API] Добавлен файл %s (размер: %d байт)", filenames[i], len(fileBytes))
	}

	err := writer.Close()
	if err != nil {
		return nil, fmt.Errorf("ошибка закрытия writer: %w", err)
	}

	url := fmt.Sprintf("%s/api/process-batch/", c.baseURL)
	req, err := http.NewRequest("POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса: %w", err)
	}

	req.Header.Set("Content-Type", writer.FormDataContentType())

	log.Printf("[API] POST %s", url)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка отправки запроса: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	log.Printf("[API] Получен ответ: статус %d", resp.StatusCode)

	if resp.StatusCode != http.StatusOK {
		var errResp ErrorResponse
		if err := json.Unmarshal(respBody, &errResp); err == nil && errResp.Detail != "" {
			return nil, fmt.Errorf("ошибка API: %s", errResp.Detail)
		}
		return nil, fmt.Errorf("ошибка API: статус %d", resp.StatusCode)
	}

	var result BatchProcessResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("ошибка парсинга ответа: %w", err)
	}

	log.Printf("[API] Пакетная обработка успешна: %d файлов", len(result.Results))
	return &result, nil
}

func (c *APIClient) HealthCheck() error {
	url := fmt.Sprintf("%s/health", c.baseURL)

	resp, err := c.httpClient.Get(url)
	if err != nil {
		return fmt.Errorf("API недоступен: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("API вернул статус %d", resp.StatusCode)
	}

	log.Printf("[API] Health check успешен")
	return nil
}

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

type ErrorResponse struct {
	Detail string `json:"detail"`
}

func NewAPIClient(baseURL string) *APIClient {
	return &APIClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
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

	log.Printf("[API] Файл успешно обработан методом: %v", result.Data["method"])
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

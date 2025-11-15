package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	TelegramToken  string
	APIBaseURL     string
	LogLevel       string
	MaxFileSizeMB  int64
	SupportContact string
}

func Load() (*Config, error) {
	_ = godotenv.Load()

	token := os.Getenv("TELEGRAM_BOT_TOKEN")
	if token == "" {
		return nil, fmt.Errorf("TELEGRAM_BOT_TOKEN не установлен")
	}

	apiBaseURL := os.Getenv("API_BASE_URL")
	if apiBaseURL == "" {
		apiBaseURL = "http://localhost:8000"
	}

	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel == "" {
		logLevel = "info"
	}

	maxFileSizeStr := os.Getenv("MAX_FILE_SIZE_MB")
	maxFileSizeMB := int64(10)
	if maxFileSizeStr != "" {
		if size, err := strconv.ParseInt(maxFileSizeStr, 10, 64); err == nil {
			maxFileSizeMB = size
		}
	}

	return &Config{
		TelegramToken:  token,
		APIBaseURL:     apiBaseURL,
		LogLevel:       logLevel,
		MaxFileSizeMB:  maxFileSizeMB,
		SupportContact: "@asdgofuckbiz",
	}, nil
}

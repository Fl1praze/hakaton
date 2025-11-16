package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/hakaton/pdf-bot/internal/clients"
	"github.com/hakaton/pdf-bot/internal/config"
	"github.com/hakaton/pdf-bot/internal/handlers"
	"github.com/hakaton/pdf-bot/internal/services"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Println("===========================================")
	log.Println("   PDF Чек Бот - Запуск")
	log.Println("===========================================")

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("❌ Ошибка загрузки конфигурации: %v", err)
	}
	log.Printf("✅ Конфигурация загружена")
	log.Printf("   API URL: %s", cfg.APIBaseURL)
	log.Printf("   Max File Size: %d МБ", cfg.MaxFileSizeMB)

	apiClient := clients.NewAPIClient(cfg.APIBaseURL)
	log.Printf("✅ API клиент создан")

	if err := apiClient.HealthCheck(); err != nil {
		log.Printf("⚠️  Предупреждение: API недоступен: %v", err)
		log.Printf("   Убедитесь что backend запущен: docker-compose up -d")
	} else {
		log.Printf("✅ API доступен и работает")
	}

	pdfService := services.NewPDFService(apiClient, cfg.MaxFileSizeMB)
	log.Printf("✅ PDF сервис создан")

	bot, err := tgbotapi.NewBotAPI(cfg.TelegramToken)
	if err != nil {
		log.Fatalf("❌ Ошибка создания бота: %v", err)
	}

	log.Printf("✅ Telegram бот авторизован: @%s", bot.Self.UserName)

	if cfg.LogLevel == "debug" {
		bot.Debug = true
		log.Printf("🐛 Debug режим включен")
	}

	handler := handlers.NewHandler(bot, pdfService, cfg.SupportContact)
	log.Printf("✅ Обработчик сообщений создан")

	updateConfig := tgbotapi.NewUpdate(0)
	updateConfig.Timeout = 60

	updates := bot.GetUpdatesChan(updateConfig)

	log.Println("===========================================")
	log.Println("   🤖 Бот запущен и готов к работе!")
	log.Println("===========================================")

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		for update := range updates {

			go func(upd tgbotapi.Update) {
				defer func() {
					if r := recover(); r != nil {
						log.Printf("❌ Паника при обработке update: %v", r)
					}
				}()
				handler.HandleUpdate(upd)
			}(update)
		}
	}()

	<-sigChan
	log.Println("\n===========================================")
	log.Println("   📴 Получен сигнал завершения")
	log.Println("   Останавливаю бота...")
	log.Println("===========================================")

	bot.StopReceivingUpdates()
	log.Println("✅ Бот остановлен")
}

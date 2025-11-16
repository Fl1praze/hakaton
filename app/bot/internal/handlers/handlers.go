package handlers

import (
	"fmt"
	"log"
	"strings"
	"time"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/hakaton/pdf-bot/internal/services"
)

type Handler struct {
	bot            *tgbotapi.BotAPI
	pdfService     *services.PDFService
	supportContact string
	mediaGroups    map[string][]*tgbotapi.Message // Хранение media group сообщений
}

func NewHandler(bot *tgbotapi.BotAPI, pdfService *services.PDFService, supportContact string) *Handler {
	return &Handler{
		bot:            bot,
		pdfService:     pdfService,
		supportContact: supportContact,
		mediaGroups:    make(map[string][]*tgbotapi.Message),
	}
}

func (h *Handler) HandleUpdate(update tgbotapi.Update) {

	if update.CallbackQuery != nil {
		h.handleCallbackQuery(update.CallbackQuery)
		return
	}

	if update.Message == nil {
		return
	}

	if update.Message.IsCommand() {
		h.handleCommand(update.Message)
		return
	}

	if update.Message.Document != nil {
		// Проверяем, является ли это частью Media Group
		if update.Message.MediaGroupID != "" {
			h.handleMediaGroup(update.Message)
		} else {
			h.handleDocument(update.Message)
		}
		return
	}

	h.sendHelpMessage(update.Message.Chat.ID)
}

func (h *Handler) handleCommand(message *tgbotapi.Message) {
	switch message.Command() {
	case "start":
		h.handleStart(message)
	case "help":
		h.sendHelpMessage(message.Chat.ID)
	default:
		h.sendMessage(message.Chat.ID, "❓ Неизвестная команда. Используйте /start")
	}
}

func (h *Handler) handleStart(message *tgbotapi.Message) {
	log.Printf("[Handler] Команда /start от пользователя %d", message.From.ID)

	welcomeText := `👋 <b>Добро пожаловать в PDF Чек Бот!</b>

Я помогу вам быстро извлечь данные из PDF чеков. 
Использую современные технологии ML и OCR для точного распознавания.

<b>Что я умею:</b>
✅ Извлекать ИНН организации
✅ Определять название поставщика
✅ Находить номер документа и дату
✅ Рассчитывать итоговую сумму
✅ Извлекать контактные данные

<b>Выберите действие:</b>`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📄 Загрузить PDF чек", "upload_pdf"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL("💬 Тех. поддержка", "https://t.me/"+strings.TrimPrefix(h.supportContact, "@")),
		),
	)

	msg := tgbotapi.NewMessage(message.Chat.ID, welcomeText)
	msg.ParseMode = "HTML"
	msg.ReplyMarkup = keyboard

	if _, err := h.bot.Send(msg); err != nil {
		log.Printf("[Handler] Ошибка отправки приветственного сообщения: %v", err)
	}
}

func (h *Handler) handleCallbackQuery(query *tgbotapi.CallbackQuery) {
	log.Printf("[Handler] Callback query: %s от пользователя %d", query.Data, query.From.ID)

	callback := tgbotapi.NewCallback(query.ID, "")
	if _, err := h.bot.Request(callback); err != nil {
		log.Printf("[Handler] Ошибка ответа на callback: %v", err)
	}

	switch query.Data {
	case "upload_pdf":
		h.handleUploadPDFRequest(query.Message.Chat.ID)
	}
}

func (h *Handler) handleUploadPDFRequest(chatID int64) {
	text := `📤 <b>Загрузка PDF чека</b>

Пожалуйста, отправьте мне PDF файл с чеком как <b>документ</b>.

<i>Примечание: максимальный размер файла - 10 МБ</i>`

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "HTML"

	if _, err := h.bot.Send(msg); err != nil {
		log.Printf("[Handler] Ошибка отправки сообщения: %v", err)
	}
}

func (h *Handler) handleDocument(message *tgbotapi.Message) {
	doc := message.Document
	log.Printf("[Handler] Получен документ: %s (размер: %d байт) от пользователя %d",
		doc.FileName, doc.FileSize, message.From.ID)

	if !strings.HasSuffix(strings.ToLower(doc.FileName), ".pdf") {
		h.sendMessage(message.Chat.ID, "❌ Пожалуйста, отправьте файл в формате PDF")
		return
	}

	maxSize := int64(10 * 1024 * 1024)
	if doc.FileSize > int(maxSize) {
		h.sendMessage(message.Chat.ID, "❌ Файл слишком большой. Максимальный размер: 10 МБ")
		return
	}

	processingMsg := h.sendMessage(message.Chat.ID, "⏳ Обрабатываю PDF... Пожалуйста, подождите.")

	fileConfig := tgbotapi.FileConfig{FileID: doc.FileID}
	file, err := h.bot.GetFile(fileConfig)
	if err != nil {
		log.Printf("[Handler] Ошибка получения файла: %v", err)
		h.editMessage(message.Chat.ID, processingMsg.MessageID, "❌ Ошибка получения файла. Попробуйте еще раз.")
		return
	}

	fileURL := file.Link(h.bot.Token)

	result, err := h.pdfService.ProcessPDFFromURL(fileURL, doc.FileName)
	if err != nil {
		log.Printf("[Handler] Ошибка обработки PDF: %v", err)
		errorMsg := fmt.Sprintf("❌ <b>Ошибка обработки PDF</b>\n\n%s\n\n<i>Попробуйте другой файл или обратитесь в поддержку.</i>", err.Error())
		h.editMessage(message.Chat.ID, processingMsg.MessageID, errorMsg)
		return
	}

	h.editMessage(message.Chat.ID, processingMsg.MessageID, result)

	h.sendActionKeyboard(message.Chat.ID)
}

func (h *Handler) sendActionKeyboard(chatID int64) {
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📄 Загрузить еще один PDF", "upload_pdf"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonURL("💬 Тех. поддержка", "https://t.me/"+strings.TrimPrefix(h.supportContact, "@")),
		),
	)

	msg := tgbotapi.NewMessage(chatID, "Выберите действие:")
	msg.ReplyMarkup = keyboard

	if _, err := h.bot.Send(msg); err != nil {
		log.Printf("[Handler] Ошибка отправки клавиатуры: %v", err)
	}
}

func (h *Handler) sendHelpMessage(chatID int64) {
	helpText := `ℹ️ <b>Справка</b>

<b>Как использовать бота:</b>
1. Нажмите кнопку "Загрузить PDF чек"
2. Отправьте PDF файл как документ
3. Получите извлеченные данные

<b>Команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку

<b>Поддержка:</b>
По вопросам обращайтесь: ` + h.supportContact

	msg := tgbotapi.NewMessage(chatID, helpText)
	msg.ParseMode = "HTML"

	if _, err := h.bot.Send(msg); err != nil {
		log.Printf("[Handler] Ошибка отправки справки: %v", err)
	}
}

func (h *Handler) sendMessage(chatID int64, text string) tgbotapi.Message {
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "HTML"

	sentMsg, err := h.bot.Send(msg)
	if err != nil {
		log.Printf("[Handler] Ошибка отправки сообщения: %v", err)
	}
	return sentMsg
}

func (h *Handler) editMessage(chatID int64, messageID int, text string) {
	msg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	msg.ParseMode = "HTML"

	if _, err := h.bot.Send(msg); err != nil {
		log.Printf("[Handler] Ошибка редактирования сообщения: %v", err)
	}
}

func (h *Handler) handleMediaGroup(message *tgbotapi.Message) {
	mediaGroupID := message.MediaGroupID
	log.Printf("[Handler] Получен документ из Media Group: %s", mediaGroupID)

	// Сохраняем сообщение в группе
	h.mediaGroups[mediaGroupID] = append(h.mediaGroups[mediaGroupID], message)

	// Проверяем, не обработана ли уже эта группа
	if len(h.mediaGroups[mediaGroupID]) == 1 {
		// Это первый файл в группе, запускаем обработку через 1 секунду
		go func(groupID string, chatID int64) {
			// Задержка для сбора всех файлов (уменьшено с 2 до 1 секунды)
			log.Printf("[Handler] Ожидание завершения Media Group %s...", groupID)
			time.Sleep(1 * time.Second)

			messages, exists := h.mediaGroups[groupID]
			if !exists || len(messages) == 0 {
				return
			}

			log.Printf("[Handler] Обработка Media Group %s: %d файлов", groupID, len(messages))

			// Фильтруем только PDF файлы
			var pdfMessages []*tgbotapi.Message
			for _, msg := range messages {
				if strings.HasSuffix(strings.ToLower(msg.Document.FileName), ".pdf") {
					pdfMessages = append(pdfMessages, msg)
				}
			}

			if len(pdfMessages) == 0 {
				h.sendMessage(chatID, "❌ В отправленных файлах нет PDF документов")
				delete(h.mediaGroups, groupID)
				return
			}

			// Проверяем размеры файлов
			maxSize := int64(10 * 1024 * 1024)
			for _, msg := range pdfMessages {
				if msg.Document.FileSize > int(maxSize) {
					h.sendMessage(chatID, fmt.Sprintf("❌ Файл %s слишком большой. Максимальный размер: 10 МБ", msg.Document.FileName))
					delete(h.mediaGroups, groupID)
					return
				}
			}

			processingMsg := h.sendMessage(chatID, fmt.Sprintf("⏳ Обрабатываю %d PDF файлов... Пожалуйста, подождите.", len(pdfMessages)))

			// Скачиваем все файлы
			var fileURLs []string
			var filenames []string

			for _, msg := range pdfMessages {
				fileConfig := tgbotapi.FileConfig{FileID: msg.Document.FileID}
				file, err := h.bot.GetFile(fileConfig)
				if err != nil {
					log.Printf("[Handler] Ошибка получения файла %s: %v", msg.Document.FileName, err)
					h.editMessage(chatID, processingMsg.MessageID, fmt.Sprintf("❌ Ошибка получения файла %s", msg.Document.FileName))
					delete(h.mediaGroups, groupID)
					return
				}

				fileURLs = append(fileURLs, file.Link(h.bot.Token))
				filenames = append(filenames, msg.Document.FileName)
			}

			// Обрабатываем все файлы пакетом
			result, err := h.pdfService.ProcessMultiplePDFsFromURLs(fileURLs, filenames)
			if err != nil {
				log.Printf("[Handler] Ошибка пакетной обработки: %v", err)
				errorMsg := fmt.Sprintf("❌ <b>Ошибка пакетной обработки</b>\n\n%s", err.Error())
				h.editMessage(chatID, processingMsg.MessageID, errorMsg)
				delete(h.mediaGroups, groupID)
				return
			}

			h.editMessage(chatID, processingMsg.MessageID, result)
			h.sendActionKeyboard(chatID)

			// Очищаем обработанную группу
			delete(h.mediaGroups, groupID)
		}(mediaGroupID, message.Chat.ID)
	}
}

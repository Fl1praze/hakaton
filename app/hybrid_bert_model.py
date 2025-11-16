"""
Гибридная BERT модель для извлечения данных из финансовых документов
Комбинирует ML подход (BERT + classifier) с надёжным regex
"""

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
from pathlib import Path
import re
from typing import Dict, Any, Optional
import json


class HybridBERTExtractor:
    """
    Гибридный подход:
    1. BERT embeddings → ML classifier (определяет НАЛИЧИЕ полей)
    2. Regex → извлекает ЗНАЧЕНИЯ полей
    3. Confidence scoring → комбинирует результаты
    """
    
    def __init__(self):
        self.model_name = "DeepPavlov/rubert-base-cased"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # основные компоненты
        self.tokenizer = None
        self.bert = None
        self.classifier = None
        self.ml_enabled = False
        
        print(f"[HYBRID] инициализация гибридной модели...")
        print(f"[HYBRID] устройство: {self.device}")
        
        # грузим bert и tokenizer
        self._load_bert()
        
        # пробуем подхватить обученный classifier
        self._load_classifier()
    
    def _load_bert(self):
        """грузит bert модель"""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.bert = AutoModel.from_pretrained(self.model_name)
            self.bert.to(self.device)
            self.bert.eval()
            
            # замораживаем bert, обучать его не будем
            for param in self.bert.parameters():
                param.requires_grad = False
            
            print(f"[OK] BERT загружен: {self.model_name}")
        except Exception as e:
            print(f"[WARNING] Не удалось загрузить BERT: {e}")
    
    def _load_classifier(self):
        """грузит готовый classifier если он есть"""
        try:
            model_path = Path(__file__).parent / "models" / "few_shot_classifier" / "model.pt"
            
            if not model_path.exists():
                print(f"[INFO] Обученный classifier не найден: {model_path}")
                return
            
            # локальный класс, такой же как при обучении
            class ReceiptClassifier(nn.Module):
                def __init__(self, bert_model_name: str):
                    super().__init__()
                    self.bert = AutoModel.from_pretrained(bert_model_name)
                    for param in self.bert.parameters():
                        param.requires_grad = False
                    
                    hidden_size = self.bert.config.hidden_size
                    self.has_inn = nn.Linear(hidden_size, 1)
                    self.has_total = nn.Linear(hidden_size, 1)
                    self.has_date = nn.Linear(hidden_size, 1)
                    self.has_vendor = nn.Linear(hidden_size, 1)
                    self.dropout = nn.Dropout(0.3)
                
                def forward(self, input_ids, attention_mask):
                    outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
                    pooled_output = outputs.pooler_output
                    x = self.dropout(pooled_output)
                    
                    return {
                        'has_inn': torch.sigmoid(self.has_inn(x)),
                        'has_total': torch.sigmoid(self.has_total(x)),
                        'has_date': torch.sigmoid(self.has_date(x)),
                        'has_vendor': torch.sigmoid(self.has_vendor(x))
                    }
            
            # создаем модель
            self.classifier = ReceiptClassifier(self.model_name)
            
            # загружаем веса с диска
            checkpoint = torch.load(model_path, map_location=self.device)
            self.classifier.load_state_dict(checkpoint['model_state_dict'])
            self.classifier.to(self.device)
            self.classifier.eval()
            
            self.ml_enabled = True
            print(f"[OK] classifier загружен из {model_path.name}")
            print(f"[OK] ml компонент активен")
            
        except Exception as e:
            import traceback
            print(f"[WARNING] Classifier не загружен: {e}")
            print(f"[DEBUG] {traceback.format_exc()}")
            print(f"[INFO] Используется только regex")
    
    def get_ml_confidence(self, text: str) -> Dict[str, float]:
        """
        Получает ML confidence scores для каждого поля
        Возвращает вероятности от 0 до 1
        """
        if not self.ml_enabled or not self.bert or not self.classifier:
            return {}
        
        try:
            # Токенизация
            encoding = self.tokenizer(
                text[:512],
                max_length=512,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            ).to(self.device)
            
            # Forward pass
            with torch.no_grad():
                outputs = self.classifier(
                    encoding['input_ids'],
                    encoding['attention_mask']
                )
            
            # Извлекаем confidence scores
            confidence = {
                'inn': outputs['has_inn'].item(),
                'total': outputs['has_total'].item(),
                'date': outputs['has_date'].item(),
                'vendor': outputs['has_vendor'].item()
            }
            
            return confidence
            
        except Exception as e:
            print(f"[WARNING] ML confidence failed: {e}")
            return {}
    
    def extract_with_regex(self, text: str) -> Dict[str, Any]:
        """
        Извлечение через regex (улучшенная версия)
        """
        result = {}
        
        # ИНН (10 или 12 цифр)
        inn_match = re.search(r'\bИНН[:\s]*(\d{10}|\d{12})\b', text, re.IGNORECASE)
        if inn_match:
            result['inn'] = inn_match.group(1)
        
        # Дата
        date_patterns = [
            r'\b(\d{2}[.]\d{2}[.]\d{4})\b',
            r'\b(\d{2}[.]\d{2}[.]\d{2})\b',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                result['date'] = match.group(1)
                break
        
        # Время
        time_match = re.search(r'\b(\d{2}:\d{2}:\d{2})\b', text)
        if time_match:
            result['time'] = time_match.group(1)
        elif re.search(r'\b(\d{2}:\d{2})\b', text):
            result['time'] = re.search(r'\b(\d{2}:\d{2})\b', text).group(1)
        
        # Сумма (улучшенный алгоритм для МИЛЛИОНОВ, чеков и банковских операций)
        all_totals = []
        total_patterns = [
            # Чеки с миллионами (1 659 649,00)
            r'(?:ИТОГО?|СУММА|TOTAL|ВСЕГО|Итого?|К оплате|Всего к оплате|Сумма заказа)[:\s=]*((?:\d{1,3}[\s]\d{3}[\s]\d{3}|[\d\s]{1,15})[.,]\d{2})\s*(?:₽|руб|RUB|Р|P)?',
            # Обычные чеки
            r'(?:ИТОГО?|СУММА|TOTAL|ВСЕГО|Итого?|Сумма заказа)[:\s=]*((?:\d{1,3}[\s,])*\d+[.,]\d{2})\s*(?:₽|руб|RUB|Р|P)?',
            r'(?:Электронный\s+платеж|Оплата)[:\s]*((?:\d{1,3}[\s,])*\d+[.,]\d{2})',
            # Банковские операции
            r'(?:Сумма в валюте карты|Сумма операции|К оплате)[:\s]*((?:\d{1,3}[\s,])*\d+[.,]\d{2})',
            # Суммы в формате "150,00 RUB" на отдельной строке
            r'(?:^|\n)\s*((?:\d{1,3}[\s,])*\d+[.,]\d{2})\s*(?:RUB|руб|₽|Р)\s*(?:\n|$)',
            r'((?:\d{1,3}[\s,])+\d{2,}[.,]\d{2})\s*(?:₽|руб|RUB)',
            # Чеки/квитанции без копеек: "Итого 2 600 ₽" (OCR может давать "i" вместо "₽")
            r'(?:ИТОГО?|СУММА|ВСЕГО|Итого?|К оплате|Всего к оплате|Сумма заказа)[:\s=]*((?:\d{1,3}[\s]\d{3}|\d{2,6}))\s*(?:₽|руб|RUB|Р|P|i)?',
        ]
        
        for pattern in total_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1).replace(',', '.').replace(' ', '')
                try:
                    num_val = float(value)
                    if num_val > 50:
                        all_totals.append((num_val, value))
                except:
                    pass
        
        if all_totals:
            all_totals.sort(reverse=True)
            result['total'] = all_totals[0][1]
        
        # Email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            result['email'] = email_match.group(0)
        
        # Телефон
        phone_match = re.search(r'\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', text)
        if phone_match:
            result['phone'] = phone_match.group(0)
        
        # Поставщик
        vendor_patterns = [
            r'((?:ООО|ИП|ПАО|АО|ЗАО)\s+["\"]?[А-ЯЁа-яё\s\-]{3,50}["\"]?)',
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text)
            if match:
                vendor = match.group(1).strip().replace('"', '').replace('"', '').strip()
                if len(vendor) > 5:
                    result['vendor'] = vendor
                    break
        
        # ОФД
        ofd_patterns = [
            r'ФНС[:\s]+([a-z0-9\-\.]+\.[a-z]{2,})',
            r'((?:ofd|nalog|taxcom|platformaofd)\.[a-z]{2,})',
        ]
        for pattern in ofd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result['ofd'] = match.group(1)
                break
        
        return result
    
    def extract_key_value_pairs(self, text: str) -> Dict[str, str]:
        """Извлекает произвольные пары ключ-значение (только полезные!)"""
        pairs = {}
        
        # Расширенный список стоп-слов (убираем мусор)
        stop_keys = {
            "ПРИЗНАК", "РАСЧЕТ", "ПРЕДМЕТА", "ЛИЦЕНЗИЯ", "БАНКА", "РОССИИ",
            "ФЕДЕРАЦИИ", "ОКРУГУ", "СООБЩАЕТ", "БЫЛА", "СОВЕРШЕНА", "ПО",
            "ОПЕРАЦИЯ", "КАРТЕ", "ВЛАДЕЛЬЦЕМ", "КОТОРОЙ", "ЯВЛЯЕТСЯ"
        }
        
        # Полезные ключи (белый список)
        useful_keys = {
            "ФН", "ФД", "ФПД", "РН ККТ", "СМЕНА", "ЧЕК", "КАССИР",
            "АДРЕС", "МЕСТО", "САЙТ", "КПП", "БИК", "СЧЕТ",
            "ТОВАР", "УСЛУГА", "СНО", "СИСТЕМА НАЛОГООБЛОЖЕНИЯ"
        }
        
        patterns = [
            # Короткие аббревиатуры с номерами
            r"((?:ФН|ФД|ФПД|РН ККТ|БИК|КПП))[:\s№]+(\d+)",
            # Кассовый чек с номером
            r"(Кассовый\s+чек)\s+№\s*(\d+)",
            # Полезные поля
            r"((?:СМЕНА|ЧЕК|КАССИР|АДРЕС|МЕСТО|САЙТ|СНО))[:\s№]+([^\n]{3,60}?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                key = re.sub(r'\s+', ' ', match.group(1).strip().upper())
                value = re.sub(r'\s+', ' ', match.group(2).strip())
                
                # Фильтры
                if len(value) < 2 or len(value) > 100:
                    continue
                
                # Проверяем стоп-слова
                if any(stop in key for stop in stop_keys):
                    continue
                
                # Проверяем что это не часть предложения
                if value.count(' ') > 10:  # Слишком много слов = предложение
                    continue
                
                # Убираем значения которые заканчиваются на предлоги
                if value.split()[-1].lower() in ['в', 'по', 'на', 'от', 'для', 'с', 'к']:
                    continue
                
                # Добавляем только если ключ полезный
                if any(useful in key for useful in useful_keys):
                    pairs[key] = value
        
        return pairs
    
    def predict(self, text: str) -> Dict[str, Any]:
        """
        Главный метод: комбинирует ML и regex
        """
        print(f"[HYBRID] Обработка документа ({len(text)} символов)...")
        
        # 1. ML confidence scores
        ml_confidence = self.get_ml_confidence(text)
        
        # 2. Regex extraction
        result = self.extract_with_regex(text)
        
        # 3. Дополнительные пары
        auto_extracted = self.extract_key_value_pairs(text)
        result['auto_extracted'] = auto_extracted
        
        # 4. Добавляем ML confidence если есть
        if ml_confidence:
            result['ml_confidence'] = ml_confidence
            print(f"[HYBRID] ML confidence: INN={ml_confidence.get('inn', 0):.2f}, "
                  f"Total={ml_confidence.get('total', 0):.2f}, "
                  f"Date={ml_confidence.get('date', 0):.2f}")
        
        print(f"[HYBRID] Найдено полей: {len([k for k in result.keys() if k not in ['auto_extracted', 'ml_confidence']])}")
        print(f"[HYBRID] Дополнительно: {len(auto_extracted)} пар")
        
        return result
    
    def get_info(self) -> Dict[str, Any]:
        """Информация о модели"""
        return {
            'model_name': self.model_name,
            'model_type': 'Hybrid BERT + Regex',
            'approach': 'ML confidence scoring + Rule-based extraction',
            'device': str(self.device),
            'ml_enabled': self.ml_enabled,
            'bert_loaded': self.bert is not None,
            'classifier_trained': self.classifier is not None
        }


# Экспортируем для использования
if __name__ == "__main__":
    print("="*80)
    print("ТЕСТ ГИБРИДНОЙ МОДЕЛИ")
    print("="*80)
    
    extractor = HybridBERTExtractor()
    
    test_text = """
    КАССОВЫЙ ЧЕК
    ООО "ДНС Ритейл"
    ИНН 2540167061
    13.11.2025 14:19:00
    ИТОГО: 10999.00 руб
    Email: info@dns-shop.ru
    ФНС: nalog.ru
    """
    
    result = extractor.predict(test_text)
    
    print("\n" + "="*80)
    print("РЕЗУЛЬТАТ:")
    print("="*80)
    print(json.dumps(result, ensure_ascii=False, indent=2))


"""
Обучаемая модель для извлечения данных из чеков
Использует гибридный подход: regex patterns + ML классификация
"""

import re
import pickle
import json
from typing import Dict, List, Tuple, Any
from pathlib import Path
import numpy as np
from datetime import datetime


class InvoiceDataExtractor:
    """
    Гибридная модель для извлечения данных из чеков
    Комбинирует regex patterns с обучаемыми весами
    """
    
    def __init__(self):
        self.patterns = {
            'inn': [
                r"ИНН[:\s]*(\d{10,12})",
                r"инн[:\s]*(\d{10,12})",
                r"ИНН\s*:\s*(\d{10,12})",
            ],
            'vendor': [
                r"(ООО\s+[\"«]?[^\"»\n]{3,50}[\"»]?)",
                r"(АО\s+[\"«]?[^\"»\n]{3,50}[\"»]?)",
                r"(ИП\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)",
                r"([А-ЯЁ][А-ЯЁ\s]{10,50}(?:ООО|АО|ИП))",
            ],
            'date': [
                r"(\d{2}\.\d{2}\.\d{4})",
                r"(\d{2}/\d{2}/\d{4})",
                r"(\d{2}\.\d{2}\.\d{2})",
                r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})",
                r"(\d{1,2}\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)\s+\d{4})",
            ],
            'total': [
                r"(?:Итого|ИТОГО|Всего|ВСЕГО|К оплате|Сумма)[:\s=]*([\d\s]+[.,]\d{2})",
                r"(?:итог|total)[:\s=]*([\d\s]+[.,]\d{2})",
                r"(?:СУММА|Сумма)[:\s]*([\d\s]+[.,]\d{2})",
            ],
        }
        
        # Веса для каждого паттерна (обучаемые)
        self.pattern_weights = {}
        for field, patterns in self.patterns.items():
            self.pattern_weights[field] = [1.0] * len(patterns)
        
        # История обучения
        self.training_history = {
            'loss': [],
            'accuracy': []
        }
        
        self.is_trained = False
        self.model_version = "1.0"
        self.training_date = None
    
    def extract_with_pattern(self, text: str, pattern: str) -> List[str]:
        """Извлекает все совпадения для паттерна"""
        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches if matches else []
    
    def extract_field(self, text: str, field: str) -> str:
        """
        Извлекает поле используя взвешенные паттерны
        """
        if field not in self.patterns:
            return "UNRECOGNIZED"
        
        candidates = []
        
        # Пробуем все паттерны с их весами
        for i, pattern in enumerate(self.patterns[field]):
            matches = self.extract_with_pattern(text, pattern)
            weight = self.pattern_weights[field][i]
            
            for match in matches:
                candidates.append({
                    'value': match,
                    'weight': weight,
                    'pattern_idx': i
                })
        
        if not candidates:
            return "UNRECOGNIZED"
        
        # Выбираем кандидата с наибольшим весом
        best_candidate = max(candidates, key=lambda x: x['weight'])
        return self._clean_value(best_candidate['value'], field)
    
    def _clean_value(self, value: str, field: str) -> Any:
        """Очистка и нормализация значения"""
        if field == 'total':
            # Преобразуем сумму в float
            try:
                clean = value.replace(' ', '').replace(',', '.')
                return float(clean)
            except:
                return value
        
        elif field == 'vendor':
            # Очищаем кавычки
            return value.strip().replace('«', '').replace('»', '').replace('"', '')
        
        return value.strip()
    
    def predict(self, text: str) -> Dict[str, Any]:
        """
        Извлекает все поля из текста
        """
        result = {}
        
        for field in ['inn', 'vendor', 'date', 'total']:
            result[field] = self.extract_field(text, field)
        
        # Дополнительные поля
        phone_match = re.search(
            r"[\+]?[7-8][\s-]?\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})",
            text
        )
        if phone_match:
            result['phone'] = f"+7{phone_match.group(1)}{phone_match.group(2)}{phone_match.group(3)}{phone_match.group(4)}"
        
        email_match = re.search(
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            text
        )
        if email_match:
            result['email'] = email_match.group(1)
        
        return result
    
    def train(self, training_data: List[Tuple[str, Dict]], epochs: int = 20):
        """
        Обучение модели на размеченных данных
        """
        print(f"\n{'='*60}")
        print(f"НАЧАЛО ОБУЧЕНИЯ МОДЕЛИ")
        print(f"{'='*60}")
        print(f"Размер датасета: {len(training_data)} примеров")
        print(f"Количество эпох: {epochs}")
        print(f"{'='*60}\n")
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            correct_predictions = 0
            total_predictions = 0
            
            # Перебираем все примеры
            for text, ground_truth in training_data:
                # Получаем предсказания
                predictions = self.predict(text)
                
                # Обновляем веса на основе ошибок
                for field in ['inn', 'vendor', 'date', 'total']:
                    if field not in ground_truth:
                        continue
                    
                    predicted = str(predictions.get(field, "UNRECOGNIZED"))
                    actual = str(ground_truth[field])
                    
                    total_predictions += 1
                    
                    # Нормализуем для сравнения
                    pred_norm = self._normalize_for_comparison(predicted)
                    actual_norm = self._normalize_for_comparison(actual)
                    
                    # Проверяем совпадение
                    is_correct = (pred_norm == actual_norm) or \
                                (pred_norm in actual_norm) or \
                                (actual_norm in pred_norm)
                    
                    if is_correct:
                        correct_predictions += 1
                        # Увеличиваем вес правильного паттерна
                        self._update_weights(text, field, predicted, reward=True)
                    else:
                        # Уменьшаем вес неправильного паттерна
                        epoch_loss += 1.0
                        self._update_weights(text, field, predicted, reward=False)
            
            # Вычисляем метрики эпохи
            avg_loss = epoch_loss / (total_predictions + 1e-6)
            accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
            
            self.training_history['loss'].append(avg_loss)
            self.training_history['accuracy'].append(accuracy)
            
            # Выводим прогресс каждые 5 эпох
            if (epoch + 1) % 5 == 0 or epoch == 0:
                print(f"Epoch {epoch + 1:2d}/{epochs} | "
                      f"Loss: {avg_loss:.4f} | "
                      f"Accuracy: {accuracy:.2f}% | "
                      f"Correct: {correct_predictions}/{total_predictions}")
        
        self.is_trained = True
        self.training_date = datetime.now().isoformat()
        
        print(f"\n{'='*60}")
        print(f"ОБУЧЕНИЕ ЗАВЕРШЕНО!")
        print(f"{'='*60}")
        print(f"Финальная точность: {self.training_history['accuracy'][-1]:.2f}%")
        print(f"Финальный loss: {self.training_history['loss'][-1]:.4f}")
        print(f"{'='*60}\n")
    
    def _normalize_for_comparison(self, s: str) -> str:
        """Нормализация строки для сравнения"""
        if not s or s == "UNRECOGNIZED":
            return ""
        return str(s).lower().strip().replace(' ', '').replace('"', '').replace('«', '').replace('»', '')
    
    def _update_weights(self, text: str, field: str, predicted_value: str, reward: bool):
        """Обновление весов паттернов"""
        if field not in self.patterns:
            return
        
        learning_rate = 0.01
        
        for i, pattern in enumerate(self.patterns[field]):
            matches = self.extract_with_pattern(text, pattern)
            
            # Если этот паттерн нашел предсказанное значение
            if predicted_value in [str(m) for m in matches]:
                if reward:
                    # Увеличиваем вес правильного паттерна
                    self.pattern_weights[field][i] += learning_rate
                else:
                    # Уменьшаем вес неправильного паттерна
                    self.pattern_weights[field][i] = max(0.1, self.pattern_weights[field][i] - learning_rate)
    
    def save(self, filepath: str):
        """Сохранение модели"""
        model_data = {
            'patterns': self.patterns,
            'pattern_weights': self.pattern_weights,
            'training_history': self.training_history,
            'is_trained': self.is_trained,
            'model_version': self.model_version,
            'training_date': self.training_date
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"✅ Модель сохранена: {filepath}")
    
    @classmethod
    def load(cls, filepath: str):
        """Загрузка модели"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        model = cls()
        model.patterns = model_data['patterns']
        model.pattern_weights = model_data['pattern_weights']
        model.training_history = model_data['training_history']
        model.is_trained = model_data['is_trained']
        model.model_version = model_data.get('model_version', '1.0')
        model.training_date = model_data.get('training_date')
        
        print(f"✅ Модель загружена: {filepath}")
        print(f"   Версия: {model.model_version}")
        print(f"   Дата обучения: {model.training_date}")
        print(f"   Финальная точность: {model.training_history['accuracy'][-1]:.2f}%")
        
        return model
    
    def get_training_info(self) -> Dict:
        """Информация о обучении"""
        return {
            'is_trained': self.is_trained,
            'model_version': self.model_version,
            'training_date': self.training_date,
            'epochs': len(self.training_history['loss']),
            'final_accuracy': self.training_history['accuracy'][-1] if self.training_history['accuracy'] else 0,
            'final_loss': self.training_history['loss'][-1] if self.training_history['loss'] else 0,
        }


if __name__ == "__main__":
    # Пример использования
    print("Тестирование модели...")
    
    model = InvoiceDataExtractor()
    
    # Тестовый текст
    test_text = """
    КАССОВЫЙ ЧЕК
    АО "ТАНДЕР"
    ИНН 2310031475
    27.09.2025 18:03
    ИТОГО: 692.88
    """
    
    result = model.predict(test_text)
    print("\nРезультат извлечения:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


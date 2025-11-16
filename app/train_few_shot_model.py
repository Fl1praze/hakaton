"""
Few-Shot Learning для извлечения данных из финансовых документов
Используем BERT embeddings (frozen) + обучаемый classifier
"""

import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
from pathlib import Path
import re
from typing import Dict, List, Tuple
import random


class ReceiptDataset(Dataset):
    """Датасет для обучения на чеках"""
    
    def __init__(self, texts: List[str], labels: List[Dict], tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label_dict = self.labels[idx]
        
        # токенизация текста
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        # превращаем метки в тензор
        label_tensor = torch.tensor([
            label_dict['has_inn'],
            label_dict['has_total'],
            label_dict['has_date'],
            label_dict['has_vendor']
        ], dtype=torch.float32)
        
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': label_tensor
        }


class ReceiptClassifier(nn.Module):
    """
    простой классификатор поверх bert embeddings
    bert заморожен, обучаем только верхний слой
    """
    
    def __init__(self, bert_model_name: str, num_classes_per_field: Dict[str, int]):
        super().__init__()
        
        # загружаем bert и замораживаем веса
        self.bert = AutoModel.from_pretrained(bert_model_name)
        for param in self.bert.parameters():
            param.requires_grad = False  # bert не обучаем
        
        hidden_size = self.bert.config.hidden_size
        
        # отдельный выход для каждого поля
        self.has_inn = nn.Linear(hidden_size, 1)     # есть инн
        self.has_total = nn.Linear(hidden_size, 1)   # есть сумма
        self.has_date = nn.Linear(hidden_size, 1)    # есть дата
        self.has_vendor = nn.Linear(hidden_size, 1)  # есть поставщик
        
        # легкий dropout
        self.dropout = nn.Dropout(0.3)
    
    def forward(self, input_ids, attention_mask):
        # берем pooled выход bert
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output  # [batch, hidden_size]
        
        # немного шума
        x = self.dropout(pooled_output)
        
        # применяем линейные головы
        has_inn = torch.sigmoid(self.has_inn(x))
        has_total = torch.sigmoid(self.has_total(x))
        has_date = torch.sigmoid(self.has_date(x))
        has_vendor = torch.sigmoid(self.has_vendor(x))
        
        return {
            'has_inn': has_inn,
            'has_total': has_total,
            'has_date': has_date,
            'has_vendor': has_vendor
        }


def augment_text(text: str) -> List[str]:
    """
    Data Augmentation: создаем вариации текста
    24 документа × 5 вариаций = 120 примеров
    """
    variations = [text]  # Оригинал
    
    # 1. Убираем лишние пробелы
    var1 = re.sub(r'\s+', ' ', text)
    variations.append(var1)
    
    # 2. Добавляем/убираем переносы строк
    var2 = text.replace('\n\n', '\n')
    variations.append(var2)
    
    # 3. Изменяем регистр некоторых слов (имитация OCR ошибок)
    words = text.split()
    if len(words) > 10:
        var3_words = words.copy()
        for i in random.sample(range(len(var3_words)), min(3, len(var3_words))):
            if var3_words[i].isupper():
                var3_words[i] = var3_words[i].lower()
        var3 = ' '.join(var3_words)
        variations.append(var3)
    
    # 4. Добавляем небольшой "шум" (лишние пробелы)
    var4 = text.replace(' ', '  ')
    variations.append(var4)
    
    return variations[:5]  # Максимум 5 вариаций


def extract_ground_truth(text: str) -> Dict[str, float]:
    """
    Извлекаем "истину" из текста (есть ли поля?)
    """
    labels = {}
    
    # ИНН
    labels['has_inn'] = 1.0 if re.search(r'\bИНН[:\s]*\d{10,12}', text, re.IGNORECASE) else 0.0
    
    # Сумма/Итого
    labels['has_total'] = 1.0 if re.search(r'(?:ИТОГО|СУММА|TOTAL)', text, re.IGNORECASE) else 0.0
    
    # Дата
    labels['has_date'] = 1.0 if re.search(r'\d{2}[.]\d{2}[.]\d{2,4}', text) else 0.0
    
    # Поставщик
    labels['has_vendor'] = 1.0 if re.search(r'(?:ООО|ИП|ПАО|АО)', text) else 0.0
    
    return labels


def prepare_training_data():
    """Подготавливаем данные для обучения"""
    print("="*80)
    print("ПОДГОТОВКА ДАННЫХ ДЛЯ FEW-SHOT LEARNING")
    print("="*80)

    # Загружаем датасет (устойчиво к разным рабочим директориям)
    script_dir = Path(__file__).parent.resolve()  # .../app
    # основной вариант: app/dataset/raw_texts.json
    dataset_path = script_dir / "dataset" / "raw_texts.json"
    # резерв: если вдруг скрипт перенесли, ищем на уровень выше
    if not dataset_path.exists():
        dataset_path = script_dir.parent / "app" / "dataset" / "raw_texts.json"

    print(f"[INFO] Ищем датасет по пути: {dataset_path}")

    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    print(f"\n[OK] Загружено {len(dataset)} документов")
    
    # Augmentation + извлечение labels
    all_texts = []
    all_labels = []
    
    for doc in dataset:
        text = doc['text']
        
        # Ground truth labels
        labels = extract_ground_truth(text)
        
        # Augmentation
        variations = augment_text(text)
        
        for var in variations:
            all_texts.append(var)
            all_labels.append(labels)
    
    print(f"[OK] После augmentation: {len(all_texts)} примеров")
    print(f"    Увеличение: {len(dataset)} -> {len(all_texts)} (x{len(all_texts)/len(dataset):.1f})")
    
    return all_texts, all_labels


def train_model(epochs=20):
    """Обучение модели"""
    print("\n" + "="*80)
    print("ОБУЧЕНИЕ FEW-SHOT МОДЕЛИ")
    print("="*80)
    
    # Подготовка данных
    texts, labels = prepare_training_data()
    
    # Разделение на train/val (80/20)
    split_idx = int(len(texts) * 0.8)
    train_texts, val_texts = texts[:split_idx], texts[split_idx:]
    train_labels, val_labels = labels[:split_idx], labels[split_idx:]
    
    print(f"\n[OK] Train: {len(train_texts)} | Val: {len(val_texts)}")
    
    # Загрузка модели и tokenizer
    model_name = "DeepPavlov/rubert-base-cased"
    print(f"\n[INFO] Загрузка {model_name}...")
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # Создаем datasets
    train_dataset = ReceiptDataset(train_texts, train_labels, tokenizer)
    val_dataset = ReceiptDataset(val_texts, val_labels, tokenizer)
    
    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=4)
    
    # Модель
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[OK] Устройство: {device}")
    
    model = ReceiptClassifier(model_name, {})
    model.to(device)
    
    # Optimizer (только для trainable параметров!)
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(trainable_params, lr=0.001)
    criterion = nn.BCELoss()
    
    print(f"[OK] Trainable параметров: {sum(p.numel() for p in trainable_params):,}")
    print(f"[OK] Frozen параметров: {sum(p.numel() for p in model.parameters() if not p.requires_grad):,}")
    
    # Training loop
    history = {'train_loss': [], 'val_loss': [], 'val_acc': []}
    
    print("\n" + "-"*80)
    print("НАЧАЛО ОБУЧЕНИЯ")
    print("-"*80)
    
    for epoch in range(epochs):
        # TRAINING
        model.train()
        train_loss = 0
        
        for batch in train_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels_batch = batch['labels'].to(device)  # [batch_size, 4]
            
            optimizer.zero_grad()
            
            # Forward
            outputs = model(input_ids, attention_mask)
            
            # Loss для каждого поля
            loss = 0
            fields = ['has_inn', 'has_total', 'has_date', 'has_vendor']
            for idx, field in enumerate(fields):
                targets = labels_batch[:, idx].unsqueeze(1)  # [batch_size, 1]
                loss += criterion(outputs[field], targets)
            
            # Backward
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # VALIDATION
        model.eval()
        val_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels_batch = batch['labels'].to(device)  # [batch_size, 4]
                
                outputs = model(input_ids, attention_mask)
                
                # Loss
                loss = 0
                fields = ['has_inn', 'has_total', 'has_date', 'has_vendor']
                for idx, field in enumerate(fields):
                    targets = labels_batch[:, idx].unsqueeze(1)  # [batch_size, 1]
                    loss += criterion(outputs[field], targets)
                    
                    # Accuracy
                    predictions = (outputs[field] > 0.5).float()
                    correct += (predictions == targets).sum().item()
                    total += targets.numel()
                
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        val_acc = correct / total
        
        # Сохраняем историю
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        
        # Вывод
        print(f"Epoch {epoch+1}/{epochs} | "
              f"Train Loss: {train_loss:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"Val Acc: {val_acc:.3f}")
    
    print("\n" + "-"*80)
    print("ОБУЧЕНИЕ ЗАВЕРШЕНО!")
    print("-"*80)
    
    # Сохранение модели (поддержка запуска из app/ и из корня)
    save_path = Path("models/few_shot_classifier")
    if not save_path.parent.exists():
        save_path = Path("app/models/few_shot_classifier")
    save_path.mkdir(parents=True, exist_ok=True)
    
    torch.save({
        'model_state_dict': model.state_dict(),
        'history': history
    }, save_path / "model.pt")
    
    # Сохраняем историю для Jupyter
    with open(save_path / "training_history.json", 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"\n[OK] Модель сохранена в {save_path}")
    print(f"[OK] История обучения: {save_path / 'training_history.json'}")
    
    # Финальные метрики
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЕ МЕТРИКИ")
    print("="*80)
    print(f"Train Loss: {history['train_loss'][-1]:.4f}")
    print(f"Val Loss:   {history['val_loss'][-1]:.4f}")
    print(f"Val Acc:    {history['val_acc'][-1]:.3f}")
    
    return model, history


if __name__ == "__main__":
    train_model(epochs=20)


import re
from collections import Counter

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


TOKEN_PATTERN = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+")


class _LSTMNetwork(nn.Module):
    def __init__(self, vocabulary_size: int, class_count: int):
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, 64, padding_idx=0)
        self.recurrent = nn.LSTM(64, 32, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(0.25)
        self.output = nn.Linear(64, class_count)

    def forward(self, tokens):
        _, (hidden, _) = self.recurrent(self.embedding(tokens))
        summary = torch.cat((hidden[-2], hidden[-1]), dim=1)
        return self.output(self.dropout(summary))


class SentimentLSTMClassifier:
    def __init__(self, epochs: int = 30):
        self.epochs = epochs
        self.max_length = 100
        self.classes_ = np.array(["Negative", "Neutral", "Positive"])
        self.vocabulary = {}
        self.network = None

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return TOKEN_PATTERN.findall(text.lower())

    def _encode(self, text: str) -> list[int]:
        tokens = [self.vocabulary.get(token, 1) for token in self.tokenize(text)[:self.max_length]]
        return tokens or [1]

    def _tensorize(self, texts) -> torch.Tensor:
        encoded = [self._encode(text) for text in texts]
        width = min(self.max_length, max(map(len, encoded)))
        result = torch.zeros((len(encoded), width), dtype=torch.long)
        for row, tokens in enumerate(encoded):
            sequence = tokens[:width]
            result[row, :len(sequence)] = torch.tensor(sequence, dtype=torch.long)
        return result

    def fit(self, texts, labels):
        torch.manual_seed(42)
        counts = Counter(token for text in texts for token in self.tokenize(text))
        self.vocabulary = {token: index + 2 for index, (token, _) in enumerate(counts.most_common())}
        self.network = _LSTMNetwork(len(self.vocabulary) + 2, len(self.classes_))
        inputs = self._tensorize(texts)
        targets = torch.tensor([int(np.where(self.classes_ == label)[0][0]) for label in labels], dtype=torch.long)
        frequencies = torch.bincount(targets, minlength=len(self.classes_)).clamp_min(1)
        weights = targets.numel() / (len(self.classes_) * frequencies.float())
        batches = DataLoader(TensorDataset(inputs, targets), batch_size=32, shuffle=True)
        optimizer = torch.optim.Adam(self.network.parameters(), lr=0.005)
        loss_function = nn.CrossEntropyLoss(weight=weights)
        self.network.train()
        for _ in range(self.epochs):
            for batch_inputs, batch_targets in batches:
                optimizer.zero_grad()
                loss = loss_function(self.network(batch_inputs), batch_targets)
                loss.backward()
                optimizer.step()
        self.network.eval()
        return self

    def predict_proba(self, texts) -> np.ndarray:
        if self.network is None:
            raise RuntimeError("The sentiment LSTM has not been trained.")
        with torch.inference_mode():
            logits = self.network(self._tensorize(texts))
            return torch.softmax(logits, dim=1).cpu().numpy()

    def predict(self, texts) -> np.ndarray:
        probabilities = self.predict_proba(texts)
        return self.classes_[probabilities.argmax(axis=1)]
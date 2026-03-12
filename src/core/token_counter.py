"""Подсчёт токенов."""

from __future__ import annotations


class TokenCounter:
    """Счётчик токенов с кешированием кодировщика."""

    _encoders: dict[str, object] = {}

    @classmethod
    def count(cls, text: str, encoding: str = "cl100k_base") -> int:
        """Точный подсчёт токенов через tiktoken."""
        if not text:
            return 0
        try:
            import tiktoken

            if encoding not in cls._encoders:
                cls._encoders[encoding] = tiktoken.get_encoding(encoding)
            enc = cls._encoders[encoding]
            return len(enc.encode(text))
        except ImportError:
            return cls.estimate(text)

    @staticmethod
    def estimate(text: str) -> int:
        """Грубая оценка: ~4 символа на токен для английского, ~2 для кода."""
        if not text:
            return 0
        return max(1, len(text) // 3)

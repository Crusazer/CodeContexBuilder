import tiktoken
from typing import List


class TokenCounter:
    @staticmethod
    def get_available_encodings() -> List[str]:
        """Возвращает список доступных кодировок (например, cl100k_base, o200k_base и т.д.)"""
        try:
            return tiktoken.list_encoding_names()
        except AttributeError:
            # Fallback для старых версий библиотеки, если метод изменится
            return ["cl100k_base", "p50k_base", "gpt2", "r50k_base"]

    @staticmethod
    def count(text: str, encoding_name: str) -> int:
        """
        Считает токены, используя выбранную кодировку.
        """
        try:
            encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Если что-то пошло не так, пробуем самую популярную
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                return 0

        try:
            return len(encoding.encode(text))
        except Exception:
            return 0

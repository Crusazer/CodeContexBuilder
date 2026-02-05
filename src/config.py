import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_app_root() -> Path:
    """
    Определяет корневую директорию приложения.
    Корректно работает как для скрипта, так и для скомпилированного EXE (PyInstaller).
    """
    if getattr(sys, "frozen", False):
        # Если приложение скомпилировано в один файл/папку
        return Path(sys.executable).parent
    else:
        # Если запуск из исходников (main.py лежит на уровень выше src/)
        return Path(__file__).resolve().parent.parent


# Корень проекта/приложения
ROOT_DIR = get_app_root()
# Файл настроек пользователя (динамический)
SETTINGS_FILE = ROOT_DIR / "settings.json"
# Файл переменных окружения (статический/секреты)
ENV_FILE = ROOT_DIR / ".env"


class AppSettings(BaseSettings):
    """
    Единый класс конфигурации.
    Приоритет (от низкого к высокому):
    1. Значения по умолчанию в полях класса.
    2. Переменные из файла .env.
    3. Системные переменные окружения (OS environment).
    4. Данные из settings.json (перезаписывают всё, если они там есть).
    """

    # --- Infrastructure / AI Settings ---
    openai_api_key: SecretStr = Field("EMPTY", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        "https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL"
    )
    model_name: str = Field("gpt-3.5-turbo", validation_alias="MODEL_NAME")

    # --- User State / UI Preferences ---
    last_project_path: Optional[str] = Field(None)
    hide_ignored_files: bool = Field(True)
    dark_mode: bool = Field(True)

    # Настройка Pydantic для чтения .env
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # Игнорировать лишние поля в .env
        case_sensitive=False,
    )

    def save(self):
        """Сохраняет текущее состояние (включая измененные ключи) в JSON."""
        data = self.model_dump(mode="json")
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"Error saving settings to {SETTINGS_FILE}: {e}")

    @classmethod
    def load_app_settings(cls) -> "AppSettings":
        """
        Фабричный метод загрузки.
        Сначала загружает .env (через Pydantic), затем обновляет полями из JSON.
        """
        # 1. Создаем инстанс с данными из .env и defaults
        settings = cls()

        # 2. Если есть settings.json, накатываем его поверх
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    json_data = json.load(f)

                # Обновляем поля, если они есть в JSON и не пустые
                update_data = {}
                for key, value in json_data.items():
                    if not hasattr(settings, key):
                        continue

                    # Специфичная логика для API Key:
                    # Если в JSON сохранено "EMPTY" (или пусто), а в ENV уже есть ключ -> не затираем ENV.
                    if key == "openai_api_key":
                        # Текущее значение (из ENV или default)
                        current_secret = settings.openai_api_key.get_secret_value()
                        # Новое значение из JSON
                        new_val = value if value else "EMPTY"

                        if new_val == "EMPTY" and current_secret != "EMPTY":
                            continue  # Оставляем значение из ENV

                    update_data[key] = value

                # Применяем обновления через construct или просто setattr
                # Pydantic v2 позволяет обновлять поля, но валидация при прямом присваивании работает иначе.
                # Проще создать новую модель с merged данными, но для mutable объекта:
                for k, v in update_data.items():
                    if k == "openai_api_key" and isinstance(v, str):
                        setattr(settings, k, SecretStr(v))
                    else:
                        setattr(settings, k, v)

            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Failed to load settings.json: {e}")

        return settings


# Глобальный объект настроек
settings = AppSettings.load_app_settings()

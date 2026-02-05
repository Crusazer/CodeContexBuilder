import json
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "CodeContextBuilder"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"


class AppSettings(BaseSettings):
    # AI Settings (можно переопределить через ENV vars)
    openai_api_key: SecretStr = Field("EMPTY", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        "http://localhost:8000/v1", validation_alias="OPENAI_BASE_URL"
    )
    model_name: str = Field("gpt-3.5-turbo", validation_alias="MODEL_NAME")

    # App State (сохраняем между запусками)
    last_project_path: Optional[str] = None
    hide_ignored_files: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    def save_to_disk(self):
        """Сохранение текущего состояния в JSON"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Экспортируем данные, сохраняя SecretStr как строки
        data = self.model_dump(mode="json")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_disk(cls) -> "AppSettings":
        """Загрузка с диска с приоритетом ENV переменных"""
        # Сначала загружаем ENV и дефолты
        settings = cls()

        # Если есть файл конфига, обновляем поля, но ENV имеют приоритет в BaseSettings,
        # поэтому здесь мы обновляем только то, что является состоянием приложения.
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    # Обновляем только dynamic state поля
                    settings.last_project_path = file_data.get("last_project_path")
                    settings.hide_ignored_files = file_data.get(
                        "hide_ignored_files", True
                    )
                    # Можно добавить логику для сохранения API ключа в файле, если нужно,
                    # но безопаснее держать их в ENV или Keyring.
            except Exception:
                pass
        return settings

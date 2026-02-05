import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parent.parent


ROOT_DIR = get_app_root()
SETTINGS_FILE = ROOT_DIR / "settings.json"
ENV_FILE = ROOT_DIR / ".env"


class AppSettings(BaseSettings):
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

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def save(self):
        """
        Сохраняет настройки в JSON.
        Принудительно извлекаем SecretStr, чтобы не сохранять '*******'.
        """
        # Сначала получаем словарь с безопасными типами
        data = self.model_dump(mode="json")

        # ПРИНУДИТЕЛЬНО перезаписываем ключ его реальным значением
        # Pydantic v2 по умолчанию скрывает SecretStr в model_dump(mode='json')
        if self.openai_api_key:
            real_key = self.openai_api_key.get_secret_value()
            if real_key == "EMPTY":
                # Если ключ пустой, лучше удалить его из json, чтобы не перекрывать .env
                if "openai_api_key" in data:
                    del data["openai_api_key"]
            else:
                data["openai_api_key"] = real_key

        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"Error saving settings to {SETTINGS_FILE}: {e}")

    @classmethod
    def load_app_settings(cls) -> "AppSettings":
        # 1. Загрузка из .env и дефолтов
        settings = cls()

        # 2. Накат поверх JSON
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    json_data = json.load(f)

                # Фильтрация мусора и обновление
                update_data = {}
                for key, value in json_data.items():
                    if not hasattr(settings, key):
                        continue

                    # КРИТИЧЕСКИ ВАЖНО: Если в файле уже сохранились звездочки, игнорируем их
                    if key == "openai_api_key" and isinstance(value, str):
                        if set(value) == {'*'}:  # Если строка состоит только из '*'
                            continue
                        if value == "EMPTY":
                            continue

                    update_data[key] = value

                # Обновляем поля. Для SecretStr нужно особое внимание при присвоении
                for k, v in update_data.items():
                    if k == "openai_api_key":
                        # Создаем новый SecretStr, чтобы Pydantic не ругался
                        setattr(settings, k, SecretStr(str(v)))
                    else:
                        setattr(settings, k, v)

            except (json.JSONDecodeError, OSError, ValidationError) as e:
                print(f"Warning: Failed to load settings.json: {e}")

        return settings


settings = AppSettings.load_app_settings()
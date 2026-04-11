"""Конфигурация проекта."""

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
WORKSPACES_DIR = ROOT_DIR / "workspaces"
SETTINGS_FILE = ROOT_DIR / "settings.json"


def ensure_dirs():
    """Создать необходимые директории."""
    for d in [
        TEMPLATES_DIR / "roles",
        TEMPLATES_DIR / "skills",
        TEMPLATES_DIR / "rules",
        TEMPLATES_DIR / "output_formats",
        WORKSPACES_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    """Загрузить настройки."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_project_path": "",
        "theme": "dark",
        "default_context_mode": "full",
        "token_warning_threshold": 100000,
        "window_geometry": None,
        "recent_projects": [],
        "backup_enabled": True,
    }


def save_settings(settings: dict[str, Any]):
    """Сохранить настройки."""
    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

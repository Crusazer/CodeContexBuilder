"""Управление шаблонами: загрузка, кеширование, CRUD с YAML frontmatter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.models.prompt_schemas import Template, TemplateCategory

logger = logging.getLogger(__name__)


class TemplateManager:
    """Менеджер шаблонов — загружает .md файлы из папки templates/."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self._cache: dict[str, Template] = {}
        self.reload()

    def reload(self):
        """Перезагрузить все шаблоны с диска."""
        self._cache.clear()

        for category in TemplateCategory:
            category_dir = self.templates_dir / category.value
            if not category_dir.exists():
                category_dir.mkdir(parents=True, exist_ok=True)
                continue

            for md_file in sorted(category_dir.rglob("*.md")):
                template = self._load_template(md_file, category)
                if template:
                    cache_key = f"{category.value}/{template.name}"
                    self._cache[cache_key] = template
                else:
                    logger.warning("Failed to load template: %s", md_file)

    def _load_template(
        self, file_path: Path, category: TemplateCategory
    ) -> Optional[Template]:
        """Загрузить один шаблон из файла с YAML frontmatter."""
        try:
            raw = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Cannot read %s: %s", file_path, e)
            return None

        name = file_path.stem
        display_name = name.replace("-", " ").title()
        description = ""
        tags: list[str] = []
        content = raw

        # Парсинг YAML frontmatter
        try:
            import frontmatter

            post = frontmatter.loads(raw)
            content = post.content
            meta = post.metadata
            display_name = meta.get("display_name", display_name)
            description = meta.get("description", "")
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
        except ImportError:
            # Fallback: парсим вручную
            content, meta = self._parse_frontmatter_manual(raw)
            display_name = meta.get("display_name", display_name)
            description = meta.get("description", "")
            tags_raw = meta.get("tags", "")
            if isinstance(tags_raw, str) and tags_raw:
                tags = [t.strip().strip("[]") for t in tags_raw.split(",")]
        except Exception as e:
            logger.warning("Frontmatter parse error in %s: %s", file_path, e)

        # Fallback для description — первая непустая строка контента
        if not description:
            for line in content.strip().split("\n"):
                s = line.strip()
                if s and not s.startswith("#"):
                    description = s[:120]
                    break

        return Template(
            name=name,
            category=category,
            display_name=display_name,
            content=content.strip(),
            file_path=file_path,
            description=description,
            tags=tags,
        )

    @staticmethod
    def _parse_frontmatter_manual(text: str) -> tuple[str, dict]:
        """Ручной парсинг YAML frontmatter без зависимости."""
        if not text.startswith("---"):
            return text, {}

        parts = text.split("---", 2)
        if len(parts) < 3:
            return text, {}

        meta_str = parts[1].strip()
        content = parts[2].strip()
        meta: dict = {}

        for line in meta_str.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                meta[key] = value

        return content, meta

    def get_by_category(self, category: TemplateCategory) -> list[Template]:
        """Получить все шаблоны категории."""
        return [t for t in self._cache.values() if t.category == category]

    def get(self, category: str, name: str) -> Optional[Template]:
        """Получить шаблон: get("roles", "worker")."""
        return self._cache.get(f"{category}/{name}")

    def get_all(self) -> dict[str, list[Template]]:
        """Все шаблоны, сгруппированные по категориям."""
        result: dict[str, list[Template]] = {cat.value: [] for cat in TemplateCategory}
        for template in self._cache.values():
            result[template.category.value].append(template)
        return result

    def save_template(self, template: Template):
        """Сохранить/обновить шаблон на диск с frontmatter."""
        template.file_path.parent.mkdir(parents=True, exist_ok=True)

        frontmatter_block = (
            f"---\n"
            f'display_name: "{template.display_name}"\n'
            f'description: "{template.description}"\n'
            f"tags: [{', '.join(template.tags)}]\n"
            f"---\n\n"
        )
        full_content = frontmatter_block + template.content
        template.file_path.write_text(full_content, encoding="utf-8")

        cache_key = f"{template.category.value}/{template.name}"
        self._cache[cache_key] = template

    def create_template(
        self,
        category: TemplateCategory,
        name: str,
        content: str,
        display_name: str = "",
        description: str = "",
        tags: list[str] | None = None,
    ) -> Template:
        """Создать новый шаблон."""
        file_path = self.templates_dir / category.value / f"{name}.md"
        template = Template(
            name=name,
            category=category,
            display_name=display_name or name.replace("-", " ").title(),
            content=content,
            file_path=file_path,
            description=description,
            tags=tags or [],
        )
        self.save_template(template)
        return template

    def delete_template(self, category: str, name: str) -> bool:
        """Удалить шаблон."""
        cache_key = f"{category}/{name}"
        template = self._cache.pop(cache_key, None)
        if template and template.file_path.exists():
            template.file_path.unlink()
            return True
        return False

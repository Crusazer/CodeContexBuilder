"""Сборщик промптов из модульных частей."""

from __future__ import annotations

from src.core.template_manager import TemplateManager
from src.core.token_counter import TokenCounter
from src.models.prompt_schemas import PromptAssembly, TemplateCategory


class PromptBuilder:
    """
    Конструктор промптов.

    builder = PromptBuilder(template_manager)
    builder.set_role("worker")
    builder.add_skill("python")
    builder.add_rule("no-placeholders")
    builder.set_output_format("search-replace-blocks")
    builder.set_context(context_text)
    builder.set_task("Добавить эндпоинт GET /users")

    assembly = builder.build()
    print(assembly.assembled_prompt)
    """

    def __init__(self, template_manager: TemplateManager):
        self.tm = template_manager
        self._assembly = PromptAssembly()

    def reset(self):
        """Сбросить сборку полностью."""
        self._assembly = PromptAssembly()

    def reset_templates(self):
        """Сбросить только шаблоны, сохранив context/task/extra."""
        ctx = self._assembly.context_text
        task = self._assembly.task_text
        extra = self._assembly.extra_instructions
        self._assembly = PromptAssembly(
            context_text=ctx,
            task_text=task,
            extra_instructions=extra,
        )

    # ─── Setters ───

    def set_role(self, name: str) -> bool:
        template = self.tm.get("roles", name)
        if template:
            self._assembly.role = template
            return True
        return False

    def clear_role(self):
        self._assembly.role = None

    def add_skill(self, name: str) -> bool:
        template = self.tm.get("skills", name)
        if template and template not in self._assembly.skills:
            self._assembly.skills.append(template)
            return True
        return False

    def remove_skill(self, name: str):
        self._assembly.skills = [s for s in self._assembly.skills if s.name != name]

    def add_rule(self, name: str) -> bool:
        template = self.tm.get("rules", name)
        if template and template not in self._assembly.rules:
            self._assembly.rules.append(template)
            return True
        return False

    def remove_rule(self, name: str):
        self._assembly.rules = [r for r in self._assembly.rules if r.name != name]

    def set_output_format(self, name: str) -> bool:
        template = self.tm.get("output_formats", name)
        if template:
            self._assembly.output_format = template
            return True
        return False

    def clear_output_format(self):
        self._assembly.output_format = None

    def set_context(self, context_text: str):
        self._assembly.context_text = context_text

    def set_task(self, task_text: str):
        self._assembly.task_text = task_text

    def set_extra_instructions(self, text: str):
        self._assembly.extra_instructions = text

    # ─── Getters ───

    def build(self) -> PromptAssembly:
        """Вернуть копию текущей сборки (immutable)."""
        return self._assembly.model_copy(deep=True)

    def get_prompt_text(self) -> str:
        return self._assembly.assembled_prompt

    def get_token_breakdown(self) -> dict[str, int]:
        return self._assembly.get_breakdown()

    def get_exact_tokens(self, encoding: str = "cl100k_base") -> int:
        return TokenCounter.count(self._assembly.assembled_prompt, encoding)

    @property
    def assembly(self) -> PromptAssembly:
        """Прямой доступ к сборке (для чтения в UI)."""
        return self._assembly

    # ─── Presets ───

    def apply_preset(
        self,
        role: str | None = None,
        skills: list[str] | None = None,
        rules: list[str] | None = None,
        output_format: str | None = None,
    ):
        """Применить пресет настроек, сохраняя context/task."""
        self.reset_templates()
        if role:
            self.set_role(role)
        for s in skills or []:
            self.add_skill(s)
        for r in rules or []:
            self.add_rule(r)
        if output_format:
            self.set_output_format(output_format)

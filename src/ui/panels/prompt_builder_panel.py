"""Панель сборки промпта: выбор роли, скиллов, правил, формата."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal

from src.core.template_manager import TemplateManager
from src.models.prompt_schemas import TemplateCategory


class PromptBuilderPanel(QWidget):
    """Панель конструктора промптов."""

    prompt_changed = pyqtSignal()

    def __init__(self, template_manager: TemplateManager, parent=None):
        super().__init__(parent)
        self.tm = template_manager
        self._skill_cbs: dict[str, QCheckBox] = {}
        self._rule_cbs: dict[str, QCheckBox] = {}
        self._init_ui()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ─── Роль ───
        role_group = QGroupBox("Role")
        role_layout = QVBoxLayout()

        self.combo_role = QComboBox()
        self.combo_role.currentIndexChanged.connect(self._on_change)
        role_layout.addWidget(self.combo_role)

        self.lbl_role_desc = QLabel("")
        self.lbl_role_desc.setWordWrap(True)
        self.lbl_role_desc.setStyleSheet("color: #888; font-size: 11px;")
        role_layout.addWidget(self.lbl_role_desc)

        role_group.setLayout(role_layout)
        layout.addWidget(role_group)

        # ─── Скиллы ───
        skills_group = QGroupBox("Skills")
        self._skills_layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(160)
        w = QWidget()
        w.setLayout(self._skills_layout)
        scroll.setWidget(w)

        outer = QVBoxLayout()
        outer.addWidget(scroll)
        skills_group.setLayout(outer)
        layout.addWidget(skills_group)

        # ─── Правила ───
        rules_group = QGroupBox("Rules")
        self._rules_layout = QVBoxLayout()

        scroll2 = QScrollArea()
        scroll2.setWidgetResizable(True)
        scroll2.setMaximumHeight(130)
        w2 = QWidget()
        w2.setLayout(self._rules_layout)
        scroll2.setWidget(w2)

        outer2 = QVBoxLayout()
        outer2.addWidget(scroll2)
        rules_group.setLayout(outer2)
        layout.addWidget(rules_group)

        # ─── Формат ───
        fmt_group = QGroupBox("Output Format")
        fmt_layout = QVBoxLayout()
        self.combo_format = QComboBox()
        self.combo_format.currentIndexChanged.connect(self._on_change)
        fmt_layout.addWidget(self.combo_format)
        fmt_group.setLayout(fmt_layout)
        layout.addWidget(fmt_group)

        # ─── Статистика ───
        stats = QFrame()
        stats.setFrameStyle(QFrame.Shape.StyledPanel)
        sl = QVBoxLayout()

        self.lbl_breakdown = QLabel("role=0, skills=0, rules=0, fmt=0")
        self.lbl_breakdown.setStyleSheet("font-size: 11px; color: #aaa;")
        sl.addWidget(self.lbl_breakdown)

        self.lbl_template_total = QLabel("Template total: ~0 tokens")
        self.lbl_template_total.setStyleSheet("font-weight: bold;")
        sl.addWidget(self.lbl_template_total)

        stats.setLayout(sl)
        layout.addWidget(stats)
        layout.addStretch()

    def _populate(self):
        """Заполнить элементы из шаблонов."""
        self.combo_role.blockSignals(True)
        self.combo_role.clear()
        self.combo_role.addItem("— No Role —", None)
        for t in self.tm.get_by_category(TemplateCategory.ROLE):
            self.combo_role.addItem(f"{t.display_name} (~{t.token_estimate}t)", t.name)
        self.combo_role.blockSignals(False)

        for t in self.tm.get_by_category(TemplateCategory.SKILL):
            cb = QCheckBox(f"{t.display_name} (~{t.token_estimate}t)")
            cb.setProperty("tname", t.name)
            cb.toggled.connect(self._on_change)
            self._skills_layout.addWidget(cb)
            self._skill_cbs[t.name] = cb

        for t in self.tm.get_by_category(TemplateCategory.RULE):
            cb = QCheckBox(f"{t.display_name} (~{t.token_estimate}t)")
            cb.setProperty("tname", t.name)
            cb.toggled.connect(self._on_change)
            self._rules_layout.addWidget(cb)
            self._rule_cbs[t.name] = cb

        self.combo_format.blockSignals(True)
        self.combo_format.clear()
        self.combo_format.addItem("— No Format —", None)
        for t in self.tm.get_by_category(TemplateCategory.OUTPUT_FORMAT):
            self.combo_format.addItem(
                f"{t.display_name} (~{t.token_estimate}t)", t.name
            )
        self.combo_format.blockSignals(False)

    def _on_change(self, *_):
        self._update_stats()
        self.prompt_changed.emit()

    def _update_stats(self):
        from src.core.token_counter import TokenCounter

        est = TokenCounter.estimate

        role_t = 0
        role_name = self.combo_role.currentData()
        if role_name:
            tmpl = self.tm.get("roles", role_name)
            if tmpl:
                role_t = est(tmpl.content)
                self.lbl_role_desc.setText(tmpl.description)
            else:
                self.lbl_role_desc.setText("")
        else:
            self.lbl_role_desc.setText("")

        skills_t = 0
        for name, cb in self._skill_cbs.items():
            if cb.isChecked():
                tmpl = self.tm.get("skills", name)
                if tmpl:
                    skills_t += est(tmpl.content)

        rules_t = 0
        for name, cb in self._rule_cbs.items():
            if cb.isChecked():
                tmpl = self.tm.get("rules", name)
                if tmpl:
                    rules_t += est(tmpl.content)

        fmt_t = 0
        fmt_name = self.combo_format.currentData()
        if fmt_name:
            tmpl = self.tm.get("output_formats", fmt_name)
            if tmpl:
                fmt_t = est(tmpl.content)

        total = role_t + skills_t + rules_t + fmt_t
        self.lbl_breakdown.setText(
            f"role={role_t}, skills={skills_t}, rules={rules_t}, fmt={fmt_t}"
        )
        self.lbl_template_total.setText(f"Template total: ~{total} tokens")

    # ─── Public API ───

    def get_selected_role(self) -> str | None:
        return self.combo_role.currentData()

    def get_selected_skills(self) -> list[str]:
        return [n for n, cb in self._skill_cbs.items() if cb.isChecked()]

    def get_selected_rules(self) -> list[str]:
        return [n for n, cb in self._rule_cbs.items() if cb.isChecked()]

    def get_selected_format(self) -> str | None:
        return self.combo_format.currentData()

    def apply_step_suggestions(
        self,
        role: str | None,
        skills: list[str],
        rules: list[str],
        output_format: str | None,
    ):
        """Программно установить выбор (из воркфлоу)."""
        self.combo_role.blockSignals(True)
        for i in range(self.combo_role.count()):
            if self.combo_role.itemData(i) == role:
                self.combo_role.setCurrentIndex(i)
                break
        else:
            self.combo_role.setCurrentIndex(0)
        self.combo_role.blockSignals(False)

        for name, cb in self._skill_cbs.items():
            cb.blockSignals(True)
            cb.setChecked(name in skills)
            cb.blockSignals(False)

        for name, cb in self._rule_cbs.items():
            cb.blockSignals(True)
            cb.setChecked(name in rules)
            cb.blockSignals(False)

        self.combo_format.blockSignals(True)
        if output_format:
            for i in range(self.combo_format.count()):
                if self.combo_format.itemData(i) == output_format:
                    self.combo_format.setCurrentIndex(i)
                    break
        else:
            self.combo_format.setCurrentIndex(0)
        self.combo_format.blockSignals(False)

        self._update_stats()
        self.prompt_changed.emit()

    def reload_templates(self):
        """Перезагрузить шаблоны."""
        self.tm.reload()

        for cb in self._skill_cbs.values():
            self._skills_layout.removeWidget(cb)
            cb.deleteLater()
        self._skill_cbs.clear()

        for cb in self._rule_cbs.values():
            self._rules_layout.removeWidget(cb)
            cb.deleteLater()
        self._rule_cbs.clear()

        self._populate()

"""Панель ввода задачи, ответа модели и применения диффов."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QGroupBox,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont


class TaskPanel(QWidget):
    """Панель задачи и ответа модели."""

    task_changed = pyqtSignal()
    copy_requested = pyqtSignal()
    parse_diffs_requested = pyqtSignal(str)  # response text
    apply_diffs_requested = pyqtSignal()
    save_step_result_requested = pyqtSignal(str)  # response text
    backup_toggled = pyqtSignal(bool)  # backup enabled changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ─── Задача ───
        task_grp = QGroupBox("Task / Задача")
        tl = QVBoxLayout()
        self.task_input = QPlainTextEdit()
        self.task_input.setPlaceholderText(
            "Опиши задачу здесь...\n\n"
            "Примеры:\n"
            "• Добавить эндпоинт GET /users/{id}/orders\n"
            "• Исправить TypeError при пустом ответе\n"
            "• Отрефакторить UserService"
        )
        self.task_input.setMaximumHeight(110)
        self.task_input.textChanged.connect(self.task_changed)
        tl.addWidget(self.task_input)
        task_grp.setLayout(tl)
        layout.addWidget(task_grp)

        # ─── Extra instructions ───
        extra_grp = QGroupBox("Extra Instructions (from previous step)")
        el = QVBoxLayout()
        el.addWidget(QLabel("Результат предыдущего шага (план/интерфейсы):"))
        self.extra_input = QPlainTextEdit()
        self.extra_input.setPlaceholderText(
            "Вставь ответ модели из предыдущего шага..."
        )
        self.extra_input.setMaximumHeight(120)
        self.extra_input.textChanged.connect(self.task_changed)
        el.addWidget(self.extra_input)
        extra_grp.setLayout(el)
        layout.addWidget(extra_grp)

        # ─── Кнопки сборки ───
        btn_row = QHBoxLayout()
        self.btn_copy = QPushButton("📋 Copy Assembled Prompt")
        self.btn_copy.setStyleSheet(
            "background-color: #2a82da; color: white; "
            "font-weight: bold; padding: 8px 16px; font-size: 13px;"
        )
        self.btn_copy.clicked.connect(self.copy_requested)
        btn_row.addWidget(self.btn_copy)
        layout.addLayout(btn_row)

        # Статистика
        self.lbl_stats = QLabel("Total: ~0 tokens | 0 chars")
        self.lbl_stats.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 4px;"
        )
        layout.addWidget(self.lbl_stats)

        # ─── Ответ модели ───
        resp_grp = QGroupBox("Model Response (paste & apply diffs)")
        rl = QVBoxLayout()
        self.response_input = QPlainTextEdit()
        self.response_input.setPlaceholderText(
            "Вставь ответ модели сюда.\n"
            "Если содержит SEARCH/REPLACE блоки — можно применить автоматически."
        )
        self.response_input.setFont(QFont("Consolas", 10))
        rl.addWidget(self.response_input)

        resp_btns = QHBoxLayout()
        self.btn_parse = QPushButton("🔍 Parse Diffs")
        self.btn_parse.clicked.connect(
            lambda: self.parse_diffs_requested.emit(self.response_input.toPlainText())
        )
        resp_btns.addWidget(self.btn_parse)

        self.btn_apply = QPushButton("✅ Apply All Diffs")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self.apply_diffs_requested)
        resp_btns.addWidget(self.btn_apply)

        self.btn_save_step = QPushButton("📝 Save as Step Result")
        self.btn_save_step.clicked.connect(
            lambda: self.save_step_result_requested.emit(
                self.response_input.toPlainText()
            )
        )
        resp_btns.addWidget(self.btn_save_step)
        rl.addLayout(resp_btns)

        # Чекбокс бэкапов
        self.chk_backup = QCheckBox("Create .bak backups before applying")
        self.chk_backup.setChecked(True)
        self.chk_backup.setToolTip(
            "Если включено, перед изменением файлов создаются .bak копии.\n"
            "Если вы используете git — можно отключить."
        )
        self.chk_backup.toggled.connect(self.backup_toggled)
        rl.addWidget(self.chk_backup)

        self.lbl_diff_status = QLabel("")
        rl.addWidget(self.lbl_diff_status)

        resp_grp.setLayout(rl)
        layout.addWidget(resp_grp)
        layout.addStretch()

    # ─── Public API ───

    def get_task(self) -> str:
        return self.task_input.toPlainText().strip()

    def get_extra(self) -> str:
        return self.extra_input.toPlainText().strip()

    def get_response(self) -> str:
        return self.response_input.toPlainText().strip()

    def set_stats(self, tokens: int, chars: int):
        self.lbl_stats.setText(f"Total: ~{tokens:,} tokens | {chars:,} chars")

    def set_diff_status(self, text: str, enable_apply: bool = False):
        self.lbl_diff_status.setText(text)
        self.btn_apply.setEnabled(enable_apply)

    def clear_response(self):
        self.response_input.clear()
        self.lbl_diff_status.setText("")
        self.btn_apply.setEnabled(False)

    def is_backup_enabled(self) -> bool:
        return self.chk_backup.isChecked()

    def set_backup_enabled(self, enabled: bool):
        self.chk_backup.setChecked(enabled)

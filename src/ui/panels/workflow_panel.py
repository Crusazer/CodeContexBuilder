"""Панель управления воркфлоу."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QPlainTextEdit,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from src.models.workflow_schemas import (
    StepStatus,
    WorkflowStep,
    BUILTIN_WORKFLOWS,
)


class WorkflowPanel(QWidget):
    """Панель управления воркфлоу."""

    workflow_start_requested = pyqtSignal(str)  # workflow key
    workflow_stop_requested = pyqtSignal()
    advance_requested = pyqtSignal(str)  # result_text
    skip_requested = pyqtSignal()
    save_workspace_requested = pyqtSignal(str)  # name
    load_workspace_requested = pyqtSignal(str)  # name

    STATUS_ICONS = {
        StepStatus.PENDING: "⬜",
        StepStatus.ACTIVE: "▶️",
        StepStatus.DONE: "✅",
        StepStatus.SKIPPED: "⏭️",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ─── Выбор воркфлоу ───
        sel_grp = QGroupBox("Workflow")
        sl = QVBoxLayout()

        self.combo_wf = QComboBox()
        self.combo_wf.addItem("— Free Mode (no workflow) —", None)
        for key, wf in BUILTIN_WORKFLOWS.items():
            self.combo_wf.addItem(f"{wf.name} — {wf.description}", key)
        sl.addWidget(self.combo_wf)

        bl = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start")
        self.btn_start.clicked.connect(self._on_start)
        bl.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        bl.addWidget(self.btn_stop)
        sl.addLayout(bl)

        sel_grp.setLayout(sl)
        layout.addWidget(sel_grp)

        # ─── Шаги ───
        steps_grp = QGroupBox("Steps")
        stl = QVBoxLayout()

        self.steps_list = QListWidget()
        self.steps_list.setMaximumHeight(180)
        stl.addWidget(self.steps_list)

        self.lbl_step_desc = QLabel("")
        self.lbl_step_desc.setWordWrap(True)
        self.lbl_step_desc.setStyleSheet("color: #ccc; padding: 4px;")
        stl.addWidget(self.lbl_step_desc)

        sbl = QHBoxLayout()
        self.btn_next = QPushButton("Next Step ➡")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self._on_advance)
        sbl.addWidget(self.btn_next)

        self.btn_skip = QPushButton("Skip ⏭")
        self.btn_skip.setEnabled(False)
        self.btn_skip.clicked.connect(self._on_skip)
        sbl.addWidget(self.btn_skip)
        stl.addLayout(sbl)

        steps_grp.setLayout(stl)
        layout.addWidget(steps_grp)

        # ─── Результат шага ───
        res_grp = QGroupBox("Step Result (summary for next step)")
        rl = QVBoxLayout()
        self.result_input = QPlainTextEdit()
        self.result_input.setPlaceholderText(
            "Краткий результат/план для передачи в следующий шаг..."
        )
        self.result_input.setMaximumHeight(100)
        rl.addWidget(self.result_input)
        res_grp.setLayout(rl)
        layout.addWidget(res_grp)

        # ─── Workspace ───
        ws_grp = QGroupBox("Sessions")
        wl = QHBoxLayout()
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._on_save_ws)
        wl.addWidget(btn_save)
        btn_load = QPushButton("📂 Load")
        btn_load.clicked.connect(self._on_load_ws)
        wl.addWidget(btn_load)
        ws_grp.setLayout(wl)
        layout.addWidget(ws_grp)

        layout.addStretch()

    # ─── Actions ───

    def _on_start(self):
        key = self.combo_wf.currentData()
        if key:
            self.workflow_start_requested.emit(key)

    def _on_stop(self):
        self.workflow_stop_requested.emit()

    def _on_advance(self):
        result = self.result_input.toPlainText().strip()
        self.advance_requested.emit(result)
        self.result_input.clear()

    def _on_skip(self):
        self.skip_requested.emit()

    def _on_save_ws(self):
        name, ok = QInputDialog.getText(self, "Save Session", "Session name:")
        if ok and name.strip():
            self.save_workspace_requested.emit(name.strip())

    def _on_load_ws(self):
        name, ok = QInputDialog.getText(self, "Load Session", "Session name:")
        if ok and name.strip():
            self.load_workspace_requested.emit(name.strip())

    # ─── Update from controller ───

    def set_workflow_active(self, active: bool):
        """Обновить состояние кнопок."""
        self.btn_start.setEnabled(not active)
        self.btn_stop.setEnabled(active)
        self.btn_next.setEnabled(active)
        self.btn_skip.setEnabled(active)
        self.combo_wf.setEnabled(not active)

    def update_steps(self, steps: list[WorkflowStep]):
        """Обновить отображение шагов."""
        self.steps_list.clear()
        for step in steps:
            icon = self.STATUS_ICONS.get(step.status, "⬜")
            item = QListWidgetItem(f"{icon} {step.id}. {step.name} [{step.role.value}]")
            if step.status == StepStatus.ACTIVE:
                item.setForeground(QColor("#2a82da"))
                self.lbl_step_desc.setText(
                    f"<b>{step.name}</b><br>"
                    f"Role: {step.role.value}<br>"
                    f"{step.description}"
                )
            elif step.status == StepStatus.DONE:
                item.setForeground(QColor("#50fa7b"))
            elif step.status == StepStatus.SKIPPED:
                item.setForeground(QColor("#888888"))
            self.steps_list.addItem(item)

    def clear_steps(self):
        self.steps_list.clear()
        self.lbl_step_desc.setText("")

    def set_result_text(self, text: str):
        """Установить текст результата (напр. из ответа модели)."""
        self.result_input.setPlainText(text[:3000])

"""Главное окно — оркестрирует все панели через контроллер."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QApplication,
    QStatusBar,
    QMenuBar,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QAction, QKeySequence

from src.controller import AppController
from src.ui.panels.file_panel import FilePanel
from src.ui.panels.prompt_builder_panel import PromptBuilderPanel
from src.ui.panels.task_panel import TaskPanel
from src.ui.panels.workflow_panel import WorkflowPanel


class MainWindow(QMainWindow):
    """Главное окно Prompt Workshop."""

    def __init__(self):
        super().__init__()
        self.ctrl = AppController()
        self._diff_blocks = []

        self.setWindowTitle("Prompt Workshop")
        self.setMinimumSize(1200, 700)

        self._init_ui()
        self._init_menu()
        self._connect_signals()
        self._init_shortcuts()

        # Открыть последний проект
        last = self.ctrl.settings.get("last_project_path", "")
        if last and Path(last).is_dir():
            self._do_open_project(last)

        self.statusBar().showMessage("Ready. Open a project folder to start.", 5000)

    def _init_ui(self):
        # Главный сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─── ЛЕВАЯ ПАНЕЛЬ: Файлы ───
        self.file_panel = FilePanel()
        self.file_panel.setMinimumWidth(220)
        self.file_panel.setMaximumWidth(400)
        splitter.addWidget(self.file_panel)

        # ─── ЦЕНТР: Превью ───
        self.preview_tabs = QTabWidget()

        # Превью файла
        self.file_preview = QTextEdit()
        self.file_preview.setReadOnly(True)
        self.file_preview.setFont(QFont("Consolas", 11))
        self.file_preview.setPlaceholderText("Select files and they will appear here.")
        self.preview_tabs.addTab(self.file_preview, "📄 File Preview")

        # Собранный промпт
        self.assembled_preview = QTextEdit()
        self.assembled_preview.setReadOnly(True)
        self.assembled_preview.setFont(QFont("Consolas", 10))
        self.assembled_preview.setPlaceholderText(
            "Assembled prompt will appear here.\n"
            "Configure role, skills, rules in Builder tab,\n"
            "write your task in Task tab, then Copy."
        )
        self.preview_tabs.addTab(self.assembled_preview, "📋 Assembled Prompt")

        # Diff превью
        self.diff_preview = QTextEdit()
        self.diff_preview.setReadOnly(True)
        self.diff_preview.setFont(QFont("Consolas", 10))
        self.preview_tabs.addTab(self.diff_preview, "🔀 Diff Preview")

        splitter.addWidget(self.preview_tabs)

        # ─── ПРАВАЯ ПАНЕЛЬ: Табы инструментов ───
        self.right_tabs = QTabWidget()

        self.builder_panel = PromptBuilderPanel(self.ctrl.template_manager)
        self.right_tabs.addTab(self.builder_panel, "🔧 Builder")

        self.task_panel = TaskPanel()
        self.right_tabs.addTab(self.task_panel, "📝 Task")

        self.workflow_panel = WorkflowPanel()
        self.right_tabs.addTab(self.workflow_panel, "🔄 Workflow")

        self.right_tabs.setMinimumWidth(300)
        self.right_tabs.setMaximumWidth(500)
        splitter.addWidget(self.right_tabs)

        splitter.setSizes([280, 600, 350])
        self.setCentralWidget(splitter)

        # Статусбар
        self.setStatusBar(QStatusBar())

    def _init_menu(self):
        menu = self.menuBar()

        # File
        file_menu = menu.addMenu("&File")
        open_act = QAction("&Open Project...", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self._menu_open_project)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # Templates
        tmpl_menu = menu.addMenu("&Templates")
        edit_act = QAction("&Edit Templates...", self)
        edit_act.triggered.connect(self._open_template_editor)
        tmpl_menu.addAction(edit_act)
        reload_act = QAction("&Reload Templates", self)
        reload_act.triggered.connect(self._reload_templates)
        tmpl_menu.addAction(reload_act)

        # Help
        help_menu = menu.addMenu("&Help")
        about_act = QAction("&About", self)
        about_act.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "Prompt Workshop",
                "Modular prompt constructor for LLM-assisted coding.\n\n"
                "Build prompts from roles, skills, rules, and project context.\n"
                "Apply SEARCH/REPLACE diffs from model responses.",
            )
        )
        help_menu.addAction(about_act)

    def _init_shortcuts(self):
        """Горячие клавиши."""
        # Ctrl+Shift+C — копировать промпт
        pass  # Handled through menu/buttons

    def _connect_signals(self):
        """Соединить сигналы всех панелей."""

        # File panel
        self.file_panel.project_opened.connect(self._do_open_project)
        self.file_panel.selection_changed.connect(self._on_files_selected)

        # Builder panel
        self.builder_panel.prompt_changed.connect(self._update_assembled)

        # Task panel
        self.task_panel.task_changed.connect(self._update_assembled)
        self.task_panel.copy_requested.connect(self._copy_prompt)
        self.task_panel.parse_diffs_requested.connect(self._parse_diffs)
        self.task_panel.apply_diffs_requested.connect(self._apply_diffs)
        self.task_panel.save_step_result_requested.connect(self._save_step_result)

        # Workflow panel
        self.workflow_panel.workflow_start_requested.connect(self._start_workflow)
        self.workflow_panel.workflow_stop_requested.connect(self._stop_workflow)
        self.workflow_panel.advance_requested.connect(self._advance_workflow)
        self.workflow_panel.skip_requested.connect(self._skip_workflow)
        self.workflow_panel.save_workspace_requested.connect(self._save_workspace)
        self.workflow_panel.load_workspace_requested.connect(self._load_workspace)

    # ─── Project ───

    def _menu_open_project(self):
        path = QFileDialog.getExistingDirectory(self, "Open Project")
        if path:
            self._do_open_project(path)

    def _do_open_project(self, path: str):
        tree = self.ctrl.open_project(path)
        self.file_panel.populate_tree(tree, path)
        self.setWindowTitle(f"Prompt Workshop — {Path(path).name}")
        self.statusBar().showMessage(f"Opened: {path}", 3000)

    # ─── File Selection ───

    def _on_files_selected(self, paths: list[Path]):
        self.ctrl.set_selected_files(paths)
        self.ctrl.context_mode = self.file_panel.get_context_mode()

        # Показать превью контекста
        if paths:
            context = self.ctrl.build_context()
            self.file_preview.setText(context)
        else:
            self.file_preview.clear()

        self._update_assembled()

    # ─── Prompt Assembly ───

    def _sync_builder_from_panel(self):
        """Синхронизировать PromptBuilder с выбором в UI."""
        b = self.ctrl.prompt_builder

        # Роль
        role = self.builder_panel.get_selected_role()
        if role:
            b.set_role(role)
        else:
            b.clear_role()

        # Скиллы — сбросить и добавить заново
        b._assembly.skills.clear()
        for s in self.builder_panel.get_selected_skills():
            b.add_skill(s)

        # Правила
        b._assembly.rules.clear()
        for r in self.builder_panel.get_selected_rules():
            b.add_rule(r)

        # Формат
        fmt = self.builder_panel.get_selected_format()
        if fmt:
            b.set_output_format(fmt)
        else:
            b.clear_output_format()

    def _update_assembled(self):
        """Пересобрать промпт и обновить превью."""
        self._sync_builder_from_panel()

        task = self.task_panel.get_task()
        extra = self.task_panel.get_extra()
        prompt = self.ctrl.assemble_prompt(task, extra)

        self.assembled_preview.setText(prompt)

        stats = self.ctrl.get_prompt_stats()
        self.task_panel.set_stats(stats["total_tokens"], stats["total_chars"])

        wf = self.ctrl.workflow_engine.active_workflow
        wf_info = f" | Workflow: {wf.name} {wf.progress}" if wf else ""
        self.statusBar().showMessage(
            f"Tokens: ~{stats['total_tokens']:,} | "
            f"Files: {stats['file_count']}{wf_info}"
        )

    # ─── Copy ───

    def _copy_prompt(self):
        self._update_assembled()
        text = self.assembled_preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage(f"✅ Copied! ~{len(text):,} chars", 3000)
            # Переключить на вкладку Assembled
            self.preview_tabs.setCurrentWidget(self.assembled_preview)
        else:
            self.statusBar().showMessage("⚠️ Nothing to copy", 3000)

    # ─── Diffs ───

    def _parse_diffs(self, text: str):
        if not text.strip():
            self.task_panel.set_diff_status("⚠️ No response text")
            return

        result = self.ctrl.parse_diffs(text)
        self._diff_blocks = result.blocks

        if result.blocks:
            # Dry run
            if self.ctrl.project_root:
                dry = self.ctrl.dry_run_diffs(result.blocks)
                ok = sum(1 for b in dry if b.applied)
                err = sum(1 for b in dry if b.error)
                self.task_panel.set_diff_status(
                    f"✅ Found {len(result.blocks)} block(s). "
                    f"Dry run: {ok} ok, {err} errors.",
                    enable_apply=ok > 0,
                )

                # Показать детали в diff preview
                lines = []
                for i, b in enumerate(dry):
                    status = "✅" if b.applied else f"❌ {b.error}"
                    lines.append(f"Block {i + 1}: {b.file_path} — {status}")
                    if b.is_new_file:
                        lines.append(f"  (new file, {len(b.replace)} chars)")
                    else:
                        lines.append(f"  SEARCH: {len(b.search)} chars")
                        lines.append(f"  REPLACE: {len(b.replace)} chars")
                    lines.append("")
                self.diff_preview.setText("\n".join(lines))
                self.preview_tabs.setCurrentWidget(self.diff_preview)
            else:
                self.task_panel.set_diff_status(
                    f"✅ Found {len(result.blocks)} block(s). Open a project to apply.",
                    enable_apply=False,
                )
        else:
            msg = "; ".join(result.warnings) if result.warnings else "No blocks found"
            self.task_panel.set_diff_status(f"⚠️ {msg}")

    def _apply_diffs(self):
        if not self._diff_blocks or not self.ctrl.project_root:
            return

        reply = QMessageBox.question(
            self,
            "Apply Diffs",
            f"Apply {len(self._diff_blocks)} change(s)?\n"
            f"Backup (.bak) files will be created.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        results = self.ctrl.apply_diffs(self._diff_blocks)
        applied = sum(1 for b in results if b.applied)
        errors = [b for b in results if b.error]

        lines = [f"Applied {applied}/{len(results)} blocks.\n"]
        for b in results:
            status = "✅ Applied" if b.applied else f"❌ {b.error}"
            lines.append(f"{b.file_path}: {status}")

        self.diff_preview.setText("\n".join(lines))
        self.preview_tabs.setCurrentWidget(self.diff_preview)

        msg = f"✅ Applied {applied}/{len(results)} diffs"
        if errors:
            msg += f" ({len(errors)} errors)"
        self.statusBar().showMessage(msg, 5000)

        # Обновить дерево
        if self.ctrl.project_root:
            tree = self.ctrl.open_project(self.ctrl.project_root)
            self.file_panel.populate_tree(tree, str(self.ctrl.project_root))

        self._diff_blocks = []
        self.task_panel.set_diff_status("", enable_apply=False)

    # ─── Workflow ───

    def _start_workflow(self, key: str):
        step = self.ctrl.start_workflow(key)
        wf = self.ctrl.workflow_engine.active_workflow

        self.workflow_panel.set_workflow_active(True)
        if wf:
            self.workflow_panel.update_steps(wf.steps)

        if step:
            self.builder_panel.apply_step_suggestions(
                role=step.role.value,
                skills=step.suggested_skills,
                rules=step.suggested_rules,
                output_format=step.suggested_output_format,
            )
            self.file_panel.combo_mode.setCurrentText(step.context_mode)
            self.right_tabs.setCurrentWidget(self.builder_panel)

        self.statusBar().showMessage(
            f"Workflow started: {key}. Step 1: {step.name if step else '?'}",
            5000,
        )
        self._update_assembled()

    def _stop_workflow(self):
        self.ctrl.stop_workflow()
        self.workflow_panel.set_workflow_active(False)
        self.workflow_panel.clear_steps()
        self.statusBar().showMessage("Workflow stopped.", 3000)

    def _advance_workflow(self, result_text: str):
        next_step = self.ctrl.advance_workflow(result_text)
        wf = self.ctrl.workflow_engine.active_workflow

        if wf:
            self.workflow_panel.update_steps(wf.steps)

        if next_step:
            self.builder_panel.apply_step_suggestions(
                role=next_step.role.value,
                skills=next_step.suggested_skills,
                rules=next_step.suggested_rules,
                output_format=next_step.suggested_output_format,
            )
            self.file_panel.combo_mode.setCurrentText(next_step.context_mode)
            self.right_tabs.setCurrentWidget(self.builder_panel)
            self.statusBar().showMessage(f"Step {next_step.id}: {next_step.name}", 5000)
        else:
            self._stop_workflow()
            QMessageBox.information(self, "Done", "Workflow completed! 🎉")

        self._update_assembled()

    def _skip_workflow(self):
        next_step = self.ctrl.skip_workflow_step()
        wf = self.ctrl.workflow_engine.active_workflow

        if wf:
            self.workflow_panel.update_steps(wf.steps)

        if next_step:
            self.builder_panel.apply_step_suggestions(
                role=next_step.role.value,
                skills=next_step.suggested_skills,
                rules=next_step.suggested_rules,
                output_format=next_step.suggested_output_format,
            )
        else:
            self._stop_workflow()

        self._update_assembled()

    def _save_step_result(self, text: str):
        """Сохранить ответ модели в поле результата воркфлоу."""
        if text:
            self.workflow_panel.set_result_text(text[:3000])
            self.statusBar().showMessage("Response saved as step result", 3000)

    def _save_workspace(self, name: str):
        try:
            self.ctrl.workflow_engine.save_workspace(name)
            self.statusBar().showMessage(f"Session saved: {name}", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _load_workspace(self, name: str):
        wf = self.ctrl.workflow_engine.load_workspace(name)
        if wf:
            self.workflow_panel.set_workflow_active(True)
            self.workflow_panel.update_steps(wf.steps)
            self.statusBar().showMessage(f"Session loaded: {name}", 3000)
        else:
            QMessageBox.warning(self, "Not Found", f"Session '{name}' not found.")

    # ─── Templates ───

    def _open_template_editor(self):
        from src.ui.dialogs.template_editor_dialog import TemplateEditorDialog

        dlg = TemplateEditorDialog(self.ctrl.template_manager, self)
        dlg.exec()
        self._reload_templates()

    def _reload_templates(self):
        self.builder_panel.reload_templates()
        self.statusBar().showMessage("Templates reloaded", 3000)

    # ─── Window ───

    def closeEvent(self, event):
        self.ctrl.save_app_settings()
        super().closeEvent(event)

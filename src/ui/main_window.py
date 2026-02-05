import os
import re
from pathlib import Path

from pydantic import SecretStr

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QTextEdit,
    QSplitter,
    QFileDialog,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QMessageBox,
    QDialog,
    QApplication,
    QRadioButton,
    QButtonGroup,
    QTabWidget,
    QPlainTextEdit,
    QDialogButtonBox,
    QMenu,
    QTreeWidgetItemIterator,  # Добавлено для обновления цветов при смене темы
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette, QSyntaxHighlighter, QTextCharFormat, QFont

from src.config import settings
from src.ui.workers import ScanWorker, AgentWorker
from src.core.processor_logic import CodeProcessor
from src.core.token_counter import TokenCounter


class FileEditDialog(QDialog):
    """Диалог для подтверждения изменения файла."""

    def __init__(self, path: str, original: str, new_code: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Allow Edit? - {path}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        info_label = QLabel(f"Agent wants to EDIT: <b>{path}</b>")
        layout.addWidget(info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Original
        orig_widget = QWidget()
        orig_layout = QVBoxLayout(orig_widget)
        orig_layout.addWidget(QLabel("Original Snippet:"))
        self.orig_edit = QTextEdit()
        self.orig_edit.setPlainText(original)
        self.orig_edit.setReadOnly(True)
        # Apply highlighter if you have one instantiated globally or pass it
        # self.orig_edit.setStyleSheet("background-color: #ffe6e6;") # Reddish tint
        orig_layout.addWidget(self.orig_edit)

        # New
        new_widget = QWidget()
        new_layout = QVBoxLayout(new_widget)
        new_layout.addWidget(QLabel("New Snippet:"))
        self.new_edit = QTextEdit()
        self.new_edit.setPlainText(new_code)
        self.new_edit.setReadOnly(True)
        # self.new_edit.setStyleSheet("background-color: #e6ffe6;") # Greenish tint
        new_layout.addWidget(self.new_edit)

        splitter.addWidget(orig_widget)
        splitter.addWidget(new_widget)
        layout.addWidget(splitter)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# --- SYNTAX HIGHLIGHTER (As before) ---
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, is_dark=True):
        super().__init__(document)
        self.rules = []
        # ... (Код подсветки синтаксиса оставлен без изменений для краткости)
        if is_dark:
            c_keyword = QColor("#ff79c6")
            c_string = QColor("#f1fa8c")
            c_comment = QColor("#6272a4")
            c_decor = QColor("#50fa7b")
            c_xml = QColor("#ffb86c")
        else:
            c_keyword = QColor("#0033b3")
            c_string = QColor("#067d17")
            c_comment = QColor("#8c8c8c")
            c_decor = QColor("#9e880d")
            c_xml = QColor("#d65e00")

        formats = {
            "kw": QTextCharFormat(),
            "str": QTextCharFormat(),
            "com": QTextCharFormat(),
            "dec": QTextCharFormat(),
            "xml": QTextCharFormat(),
        }

        formats["kw"].setForeground(c_keyword)
        formats["kw"].setFontWeight(QFont.Weight.Bold)
        formats["str"].setForeground(c_string)
        formats["com"].setForeground(c_comment)
        formats["dec"].setForeground(c_decor)
        formats["xml"].setForeground(c_xml)
        formats["xml"].setFontWeight(QFont.Weight.Bold)

        keywords = [
            r"\bdef\b",
            r"\bclass\b",
            r"\bif\b",
            r"\belse\b",
            r"\bwhile\b",
            r"\bfor\b",
            r"\breturn\b",
            r"\bimport\b",
            r"\bfrom\b",
            r"\btry\b",
            r"\bexcept\b",
            r"\bwith\b",
            r"\basync\b",
            r"\bawait\b",
            r"\bpass\b",
            r"\blambda\b",
        ]

        for pattern in keywords:
            self.rules.append((re.compile(pattern), formats["kw"]))

        self.rules.append((re.compile(r"@[^\n]+"), formats["dec"]))
        self.rules.append((re.compile(r"\".*\""), formats["str"]))
        self.rules.append((re.compile(r"'.*'"), formats["str"]))
        self.rules.append((re.compile(r"#[^\n]*"), formats["com"]))
        self.rules.append((re.compile(r"</?file[^>]*>"), formats["xml"]))
        self.rules.append((re.compile(r"</?project_structure>"), formats["xml"]))
        self.rules.append((re.compile(r"<path>.*</path>"), formats["xml"]))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# --- CONFIRMATION DIALOG ---
class FileCreationDialog(QDialog):
    def __init__(self, path: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agent wants to create a file")
        self.resize(600, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Path:</b> {path}"))
        layout.addWidget(QLabel("<b>Content:</b>"))

        text = QTextEdit()
        text.setPlainText(content)
        text.setReadOnly(True)
        # Простая подсветка для контента
        font = QFont("Consolas", 10)
        text.setFont(font)
        layout.addWidget(text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = settings
        self.current_nodes = {}
        self.selected_paths = set()
        self.cached_full_context = ""
        self.agent_worker = None  # Ссылка на воркера агента
        self.file_overrides = {}

        self.init_ui()
        self.update_theme_style()

        if self.settings.last_project_path:
            self.load_project(self.settings.last_project_path)

    def update_theme_style(self):
        # ... (Код стилей оставлен без изменений, скопируйте из оригинального файла)
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()

        if self.settings.dark_mode:
            c_bg = QColor(44, 44, 44)
            c_fg = QColor(240, 240, 240)
            c_base = QColor(30, 30, 30)
            c_hl = QColor(42, 130, 218)
            css_bg_dark = "#1e1e1e"
            css_text_color = "#f0f0f0"
            css_border = "#3a3a3a"
            css_hover = "#333333"
            css_select = "#2a82da"
            css_check_border = "#888888"
            css_check_bg = "#333333"

            palette.setColor(QPalette.ColorRole.Window, c_bg)
            palette.setColor(QPalette.ColorRole.WindowText, c_fg)
            palette.setColor(QPalette.ColorRole.Base, c_base)
            palette.setColor(QPalette.ColorRole.AlternateBase, c_bg)
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Text, c_fg)
            palette.setColor(QPalette.ColorRole.Button, c_bg)
            palette.setColor(QPalette.ColorRole.ButtonText, c_fg)
            palette.setColor(QPalette.ColorRole.Link, c_hl)
            palette.setColor(QPalette.ColorRole.Highlight, c_hl)
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        else:
            palette = QApplication.style().standardPalette()
            css_bg_dark = "#ffffff"
            css_text_color = "#000000"
            css_border = "#cccccc"
            css_hover = ""
            css_select = ""
            css_check_border = ""
            css_check_bg = ""

        app.setPalette(palette)

        if self.settings.dark_mode:
            tree_style = (
                f"QTreeWidget {{ background-color: {css_bg_dark}; color: {css_text_color}; border: 1px solid {css_border}; }}"
                f"QTreeWidget::item:hover {{ background-color: {css_hover}; }}"
                f"QTreeWidget::item:selected {{ background-color: {css_select}; }}"
                f"QTreeWidget::indicator {{ width: 14px; height: 14px; border: 1px solid {css_check_border}; border-radius: 3px; background-color: {css_check_bg}; }}"
                f"QTreeWidget::indicator:checked {{ background-color: {css_select}; border: 1px solid {css_select}; }}"
                f"QTreeWidget::indicator:unchecked:hover {{ border: 1px solid #aaaaaa; background-color: #444444; }}"
            )
            editor_style = f"QTextEdit {{ background-color: {css_bg_dark}; color: {css_text_color}; border: 1px solid {css_border}; }}"
        else:
            tree_style = ""
            editor_style = ""

        self.tree.setStyleSheet(tree_style)
        self.preview.setStyleSheet(editor_style)
        self.highlighter = PythonHighlighter(
            self.preview.document(), is_dark=self.settings.dark_mode
        )

    def toggle_theme(self):
        self.settings.dark_mode = not self.settings.dark_mode
        self.settings.save()
        self.update_theme_style()

        # Принудительно обновляем цвета меток (SKEL/FULL) в дереве,
        # так как они зависят от dark_mode в update_item_label
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if path_str:
                self.update_item_label(item, path_str)
            iterator += 1

    def init_ui(self):
        self.setWindowTitle("CodeContext Agent")
        self.resize(1350, 850)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # === LEFT (Files) ===
        left_panel = QWidget()
        l_layout = QVBoxLayout(left_panel)
        l_layout.setContentsMargins(5, 5, 5, 5)

        # Кнопки управления файлами
        buttons_layout = QHBoxLayout()

        btn_open = QPushButton("Open Folder")
        btn_open.clicked.connect(self.open_dir_dialog)
        buttons_layout.addWidget(btn_open)

        # [NEW] Кнопка сброса выбора
        btn_reset = QPushButton("Reset Selection")
        btn_reset.clicked.connect(self.reset_selection)
        buttons_layout.addWidget(btn_reset)

        l_layout.addLayout(buttons_layout)

        self.cb_ignore = QCheckBox("Hide .gitignore files")
        self.cb_ignore.setChecked(self.settings.hide_ignored_files)
        self.cb_ignore.toggled.connect(self.refresh_tree)
        l_layout.addWidget(self.cb_ignore)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Files")
        self.tree.itemChanged.connect(self.on_item_checked)
        self.tree.currentItemChanged.connect(self.on_current_item_changed)

        # Настройка контекстного меню
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        l_layout.addWidget(self.tree)

        splitter.addWidget(left_panel)

        # === CENTER (Preview) ===
        center_panel = QWidget()
        c_layout = QVBoxLayout(center_panel)
        c_layout.setContentsMargins(5, 5, 5, 5)

        preview_controls = QHBoxLayout()
        self.rb_file_view = QRadioButton("Single File Preview")
        self.rb_context_view = QRadioButton("Context Preview")
        self.rb_file_view.setChecked(True)
        self.view_group = QButtonGroup()
        self.view_group.addButton(self.rb_file_view)
        self.view_group.addButton(self.rb_context_view)
        self.view_group.buttonToggled.connect(self.update_preview_content)

        preview_controls.addWidget(self.rb_file_view)
        preview_controls.addWidget(self.rb_context_view)

        # New Save Button
        self.btn_save_file = QPushButton("Save File")
        self.btn_save_file.setEnabled(False)  # Изначально выключена
        self.btn_save_file.clicked.connect(self.save_current_file)
        preview_controls.addWidget(self.btn_save_file)

        preview_controls.addStretch()
        c_layout.addLayout(preview_controls)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        font = QFont("Consolas" if os.name == "nt" else "Menlo", 11)
        self.preview.setFont(font)

        c_layout.addWidget(self.preview)
        splitter.addWidget(center_panel)

        # === RIGHT (Controls & Agent) ===
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Tabs for Simple Docs vs Agent
        self.tabs = QTabWidget()

        # Tab 1: Settings & Simple Tools
        tab_settings = QWidget()
        ts_layout = QVBoxLayout(tab_settings)

        self.btn_theme = QPushButton("Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        ts_layout.addWidget(self.btn_theme)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Raw Code", "Skeleton (Interfaces)"])
        self.combo_mode.currentIndexChanged.connect(self.on_processing_mode_changed)
        ts_layout.addWidget(QLabel("Context Mode (Raw/Skeleton):"))
        ts_layout.addWidget(self.combo_mode)

        ai_group = QGroupBox("LLM Connection")
        form = QFormLayout()
        self.inp_url = QLineEdit(self.settings.openai_base_url)
        self.inp_key = QLineEdit(self.settings.openai_api_key.get_secret_value())
        self.inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_model = QLineEdit(self.settings.model_name)
        form.addRow("URL:", self.inp_url)
        form.addRow("Key:", self.inp_key)
        form.addRow("Model:", self.inp_model)
        ai_group.setLayout(form)
        ts_layout.addWidget(ai_group)

        stats_group = QGroupBox("Stats")
        s_l = QVBoxLayout()
        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(TokenCounter.get_available_encodings())
        self.combo_encoding.setCurrentIndex(0)
        self.combo_encoding.currentIndexChanged.connect(self.update_stats_display)
        s_l.addWidget(self.combo_encoding)
        self.lbl_char_count = QLabel("Chars: 0")
        self.lbl_token_count = QLabel("Tokens: 0")
        s_l.addWidget(self.lbl_char_count)
        s_l.addWidget(self.lbl_token_count)
        stats_group.setLayout(s_l)
        ts_layout.addWidget(stats_group)

        btn_copy = QPushButton("Copy Context")
        btn_copy.clicked.connect(self.copy_context)
        ts_layout.addWidget(btn_copy)

        ts_layout.addStretch()
        self.tabs.addTab(tab_settings, "Settings")

        # Tab 2: Agent
        tab_agent = QWidget()
        ta_layout = QVBoxLayout(tab_agent)

        ta_layout.addWidget(QLabel("Agent Instructions:"))
        self.agent_prompt_input = QPlainTextEdit()
        self.agent_prompt_input.setPlaceholderText(
            "Example: Analyze the user service and create a unit test file for it."
        )
        self.agent_prompt_input.setMaximumHeight(100)
        ta_layout.addWidget(self.agent_prompt_input)

        self.cb_reasoning = QCheckBox("Enable Reasoning Step (Plan)")
        self.cb_reasoning.setChecked(True)
        ta_layout.addWidget(self.cb_reasoning)

        self.btn_run_agent = QPushButton("Run Agent")
        self.btn_run_agent.setStyleSheet(
            "background-color: #2a82da; color: white; font-weight: bold; padding: 5px;"
        )
        self.btn_run_agent.clicked.connect(self.run_agent)
        ta_layout.addWidget(self.btn_run_agent)

        ta_layout.addWidget(QLabel("Agent Log / Output:"))
        self.agent_log_output = QTextEdit()
        self.agent_log_output.setReadOnly(True)
        if self.settings.dark_mode:
            self.agent_log_output.setStyleSheet(
                "background-color: #1e1e1e; color: #00ff00; font-family: Consolas;"
            )
        ta_layout.addWidget(self.agent_log_output)

        self.tabs.addTab(tab_agent, "Agent")

        r_layout.addWidget(self.tabs)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 600, 350])

    def reset_selection(self):
        """Снимает галочки со всех элементов и очищает список выбранных файлов."""
        self.tree.blockSignals(True)  # Блокируем сигналы для производительности

        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1

        self.tree.blockSignals(False)

        self.selected_paths.clear()
        self.update_preview_content()
        self.statusBar().showMessage("Selection cleared.", 2000)

    # ... (open_dir_dialog, load_project, refresh_tree, on_scan_done, on_processing_mode_changed - без изменений)
    def open_dir_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.load_project(path)

    def load_project(self, path):
        self.settings.last_project_path = path
        self.save_current_settings()
        self.setWindowTitle(f"CodeContext Agent - {path}")
        self.refresh_tree()

    def refresh_tree(self):
        path = self.settings.last_project_path
        if not path:
            return
        self.settings.hide_ignored_files = self.cb_ignore.isChecked()
        self.tree.clear()
        self.tree.setEnabled(False)
        self.preview.clear()
        self.worker = ScanWorker(path, self.settings.hide_ignored_files)
        self.worker.finished.connect(self.on_scan_done)
        self.worker.start()

    def on_scan_done(self, nodes):
        self.tree.setEnabled(True)
        self.current_nodes = {str(n.path): n for n in nodes}
        dirs = {}
        for n in nodes:
            parts = n.rel_path.parts
            parent = self.tree.invisibleRootItem()
            curr = Path("")
            for p in parts[:-1]:
                curr = curr / p
                s_rel = str(curr)
                if s_rel not in dirs:
                    item = QTreeWidgetItem(parent, [p])
                    item.setFlags(
                        item.flags()
                        | Qt.ItemFlag.ItemIsAutoTristate
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    dirs[s_rel] = item
                    parent = item
                else:
                    parent = dirs[s_rel]

            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            # Убран дублирующийся блок кода создания QTreeWidgetItem

            f = QTreeWidgetItem(parent, [parts[-1]])
            f.setFlags(f.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            f.setCheckState(0, Qt.CheckState.Unchecked)
            path_str = str(n.path)
            f.setData(0, Qt.ItemDataRole.UserRole, path_str)

            # ВОССТАНАВЛИВАЕМ ВИЗУАЛЬНУЮ МЕТКУ
            self.update_item_label(f, path_str)

    def on_processing_mode_changed(self):
        self.update_preview_content()

    def update_preview_content(self):
        # Генерируем полный контекст (Скелет или Полный) в зависимости от комбобокса
        # Это нужно, чтобы обновить статистику токенов и кэш
        full_context = self._generate_full_context(limit_preview=False)
        self.cached_full_context = full_context
        self.update_stats_display()

        if self.rb_file_view.isChecked():
            # Режим просмотра одного файла
            current = self.tree.currentItem()
            if current:
                self.on_current_item_changed(current, None)
            else:
                self.preview.clear()
                self.preview.setReadOnly(True)
                self.btn_save_file.setEnabled(False)
        else:
            # Режим просмотра контекста
            self.preview.setReadOnly(True)
            self.btn_save_file.setEnabled(False)

            if len(full_context) > 100000:
                self.preview.setText(
                    full_context[:100000]
                    + "\n\n... (preview truncated for UI performance, but Stats show full size) ..."
                )
            else:
                self.preview.setText(
                    full_context if full_context else "No files selected."
                )

    def update_stats_display(self):
        text = self.cached_full_context
        char_count = len(text)
        selected_encoding = self.combo_encoding.currentText() or "cl100k_base"
        token_count = TokenCounter.count(text, selected_encoding)
        self.lbl_char_count.setText(f"Chars: {char_count:,}".replace(",", " "))
        self.lbl_token_count.setText(f"Tokens: {token_count:,}".replace(",", " "))

    def on_current_item_changed(self, current, previous):
        if self.rb_context_view.isChecked():
            # В режиме контекста клик по дереву не меняет превью (превью показывает сумму выбранных)
            return

        if not current:
            self.preview.clear()
            self.preview.setReadOnly(True)
            self.btn_save_file.setEnabled(False)
            return

        path_str = current.data(0, Qt.ItemDataRole.UserRole)
        if path_str and Path(path_str).is_file():
            self.display_file_preview(Path(path_str))
        else:
            self.preview.clear()
            self.preview.setReadOnly(True)
            self.btn_save_file.setEnabled(False)

    def display_file_preview(self, path: Path):
        try:
            if CodeProcessor.is_binary(path):
                self.preview.setText("[Binary File - Editing Not Supported]")
                self.preview.setReadOnly(True)
                self.btn_save_file.setEnabled(False)
                return

            # Читаем файл целиком (без лимита), чтобы можно было безопасно редактировать
            # Внимание: для очень больших файлов это может быть медленно, но необходимо для сохранения целостности
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            self.preview.setText(content)

            # Разрешаем редактирование и сохранение для текстовых файлов
            self.preview.setReadOnly(False)
            self.btn_save_file.setEnabled(True)

        except Exception as e:
            self.preview.setText(f"[Error: {e}]")
            self.preview.setReadOnly(True)
            self.btn_save_file.setEnabled(False)

    def save_current_file(self):
        """Сохраняет содержимое редактора в текущий выбранный файл."""
        if self.rb_context_view.isChecked():
            return

        current = self.tree.currentItem()
        if not current:
            return

        path_str = current.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        path = Path(path_str)
        if not path.is_file():
            return

        content = self.preview.toPlainText()

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            self.statusBar().showMessage(f"Saved: {path.name}", 3000)

            # Обновляем статистику, так как файл изменился (он может быть в selected_paths)
            self.update_preview_content()

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{e}")

    def on_item_checked(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_paths.add(path)
            else:
                self.selected_paths.discard(path)
        # Если мы в режиме контекста, обновление галочки меняет превью.
        # Если в режиме файла - превью не меняется (оно зависит от selection), но контекст в памяти надо обновить
        self.update_preview_content()

    def _generate_full_context(self, limit_preview=False) -> str:
        if not self.settings.last_project_path:
            return ""

        out = []
        root = Path(self.settings.last_project_path)

        # 1. Project Structure (ВСЯ структура проекта, а не только выбранные файлы)
        out.append("# Project Structure")

        # Если сканирование уже прошло и есть nodes, используем их
        if self.current_nodes:
            # Сортируем все пути
            all_paths = sorted([n.path for n in self.current_nodes.values()])
            for p in all_paths:
                try:
                    rel_path = p.relative_to(root).as_posix()
                    # Отмечаем выбранные файлы звездочкой или просто выводим путь
                    # Для LLM просто наличие пути достаточно, чтобы понять структуру
                    out.append(f"{rel_path}")
                except ValueError:
                    pass
        else:
            out.append("(Project structure not yet scanned)")

        out.append("")

        # 2. File Contents (Только ВЫБРАННЫЕ файлы)
        if not self.selected_paths:
            out.append("# No files selected for content context.")
            return "\n".join(out)

        out.append("# File Contents")

        sorted_selected_paths = sorted([Path(p) for p in self.selected_paths])

        # Глобальная настройка режима
        global_mode_text = self.combo_mode.currentText()
        global_is_skeleton = global_mode_text.startswith("Skeleton")

        total_chars = 0
        LIMIT = 10000

        for p in sorted_selected_paths:
            if limit_preview and total_chars > LIMIT:
                out.append("\n... (preview truncated) ...")
                break

            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name

            # === ЛОГИКА ВЫБОРА РЕЖИМА ===
            path_str = str(p)
            override = self.file_overrides.get(path_str)

            if override == "skeleton":
                is_file_skeleton = True
            elif override == "full":
                is_file_skeleton = False
            else:
                # Если override нет, берем глобальную настройку
                is_file_skeleton = global_is_skeleton
            # ============================

            # Передаем вычисленный флаг is_file_skeleton
            content = CodeProcessor.process_file(p, is_file_skeleton)

            # Определяем язык для markdown разметки
            ext = p.suffix.lower()
            lang = "text"
            if ext in [".py", ".pyw"]:
                lang = "python"
            elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                lang = "javascript"
            elif ext in [".html", ".htm"]:
                lang = "html"
            elif ext in [".css"]:
                lang = "css"
            elif ext in [".json"]:
                lang = "json"
            elif ext in [".md"]:
                lang = "markdown"

            # Добавим визуальную пометку в сам контекст, чтобы LLM понимала (опционально)
            header_suffix = " (Skeleton)" if is_file_skeleton else ""
            out.append(f"## File: {rel}{header_suffix}")
            out.append(f"```{lang}")
            out.append(content)
            out.append("```\n")

            total_chars += len(content)

        return "\n".join(out)

    def save_current_settings(self):
        self.settings.openai_base_url = self.inp_url.text().strip()
        ui_key = self.inp_key.text().strip()
        if ui_key and ui_key != "EMPTY":
            self.settings.openai_api_key = SecretStr(ui_key)
        self.settings.model_name = self.inp_model.text().strip()
        self.settings.save()

    def copy_context(self):
        if not self.selected_paths:
            self.statusBar().showMessage("No files selected!")
            return
        self.save_current_settings()
        text = self.cached_full_context or self._generate_full_context(
            limit_preview=False
        )
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied {len(self.selected_paths)} files.")

    # --- AGENT LOGIC ---
    def run_agent(self):
        if not self.selected_paths:
            QMessageBox.warning(self, "Warning", "Select context files first.")
            return

        prompt = self.agent_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(
                self, "Warning", "Please enter instruction for the agent."
            )
            return

        self.save_current_settings()

        # Контекст генерируется на основе текущих настроек (скелет/полный)
        context = (
            self.cached_full_context
            if self.cached_full_context
            else self._generate_full_context()
        )

        self.agent_log_output.clear()
        self.agent_log_output.append(">>> Starting Agent...")
        self.btn_run_agent.setEnabled(False)

        # Инициализация воркера с текущими настройками
        self.agent_worker = AgentWorker(
            settings=self.settings,
            project_root=Path(self.settings.last_project_path),
            context=context,
            user_prompt=prompt,
            use_reasoning=self.cb_reasoning.isChecked(),
        )

        # Подключение стандартных сигналов (логи, результат, ошибки, завершение)
        self.agent_worker.log_signal.connect(self.on_agent_log)
        self.agent_worker.result_signal.connect(self.on_agent_result)
        self.agent_worker.error_signal.connect(self.on_agent_error)
        self.agent_worker.finished.connect(lambda: self.btn_run_agent.setEnabled(True))

        # --- НОВОЕ: Подключение сигналов Human-in-the-Loop ---

        # 1. Запрос на создание файла (path, content)
        self.agent_worker.request_creation_signal.connect(
            self.on_agent_creation_request
        )

        # 2. Запрос на изменение файла (path, original_snippet, new_snippet)
        self.agent_worker.request_edit_signal.connect(self.on_agent_edit_request)

        self.agent_worker.start()

    def on_agent_creation_request(self, rel_path, content):
        """Обработка запроса на СОЗДАНИЕ файла."""
        dialog = FileCreationDialog(rel_path, content, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.agent_worker.set_user_response(True)
        else:
            self.agent_worker.set_user_response(False)

    def on_agent_edit_request(self, rel_path, original, new_code):
        """Обработка запроса на РЕДАКТИРОВАНИЕ файла."""
        dialog = FileEditDialog(rel_path, original, new_code, self)
        # Можно добавить подсветку синтаксиса в диалог, если нужно
        # highlighter1 = PythonHighlighter(dialog.orig_edit.document(), self.is_dark_theme)
        # highlighter2 = PythonHighlighter(dialog.new_edit.document(), self.is_dark_theme)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.agent_worker.set_user_response(True)
        else:
            self.agent_worker.set_user_response(False)

    def on_agent_log(self, msg):
        self.agent_log_output.append(msg)
        # Прокрутка вниз
        sb = self.agent_log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_agent_result(self, result):
        self.agent_log_output.append(f"\n>>> AGENT FINISHED:\n{result}")
        # Автоматическое обновление дерева, если файлы были созданы
        self.refresh_tree()

    def on_agent_error(self, err):
        self.agent_log_output.append(f"\n>>> ERROR: {err}")
        QMessageBox.critical(self, "Agent Error", err)

    def on_agent_approval_request(self, rel_path, content):
        """Обработка сигнала Human-in-Loop из воркера."""
        dlg = FileCreationDialog(rel_path, content, self)
        res = dlg.exec()
        approved = res == QDialog.DialogCode.Accepted

        if self.agent_worker:
            self.agent_worker.set_user_response(approved)

    def show_tree_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return

        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return  # Это папка без пути или корень, пропускаем

        # Создаем меню
        menu = QMenu()

        # Действия
        action_default = menu.addAction("Use Global Default")
        action_full = menu.addAction("Force FULL Content")
        action_skel = menu.addAction("Force SKELETON")

        # Отмечаем текущее состояние галочкой в меню (опционально, для красоты)
        current_override = self.file_overrides.get(path_str)
        if current_override == "full":
            action_full.setCheckable(True)
            action_full.setChecked(True)
        elif current_override == "skeleton":
            action_skel.setCheckable(True)
            action_skel.setChecked(True)
        else:
            action_default.setCheckable(True)
            action_default.setChecked(True)

        # Запуск меню и обработка выбора
        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if action == action_default:
            self.set_file_override(item, None)
        elif action == action_full:
            self.set_file_override(item, "full")
        elif action == action_skel:
            self.set_file_override(item, "skeleton")

    def set_file_override(self, item: QTreeWidgetItem, mode: str):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        if mode is None:
            # Удаляем из словаря
            self.file_overrides.pop(path_str, None)
        else:
            self.file_overrides[path_str] = mode

        # Обновляем визуальное отображение (текст в дереве)
        self.update_item_label(item, path_str)

        # Обновляем превью, так как контекст изменился
        self.update_preview_content()

    def update_item_label(self, item: QTreeWidgetItem, path_str: str):
        """Обновляет текст элемента дерева, добавляя маркер режима."""
        # Получаем чистое имя файла (восстанавливаем из пути, чтобы убрать старые метки)
        clean_name = Path(path_str).name

        override = self.file_overrides.get(path_str)

        if override == "skeleton":
            item.setText(0, f"{clean_name} [SKEL]")
            # Проверяем тему для установки цвета
            if self.settings.dark_mode:
                item.setForeground(
                    0, QColor("#e6db74")
                )  # Светло-желтый для темной темы
            else:
                item.setForeground(
                    0, QColor("#b58900")
                )  # Оливковый/Темно-желтый для светлой
        elif override == "full":
            item.setText(0, f"{clean_name} [FULL]")
            if self.settings.dark_mode:
                item.setForeground(
                    0, QColor("#a6e22e")
                )  # Светло-зеленый для темной темы
            else:
                item.setForeground(0, QColor("#008000"))  # Темно-зеленый для светлой
        else:
            item.setText(0, clean_name)
            # Возвращаем стандартный цвет
            if self.settings.dark_mode:
                item.setForeground(0, QColor("#f0f0f0"))
            else:
                item.setForeground(0, QColor("#000000"))

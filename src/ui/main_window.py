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
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette, QSyntaxHighlighter, QTextCharFormat, QFont

from src.config import settings
from src.ui.workers import ScanWorker, AIWorker
from src.core.processor_logic import CodeProcessor
from src.core.token_counter import TokenCounter


# --- SYNTAX HIGHLIGHTER ---
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, is_dark=True):
        super().__init__(document)
        self.rules = []
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


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = settings
        self.current_nodes = {}
        self.selected_paths = set()
        self.cached_full_context = ""

        # Сначала инициализируем UI (создаем виджеты)
        self.init_ui()
        # Затем применяем стили (красим виджеты)
        self.update_theme_style()

        if self.settings.last_project_path:
            self.load_project(self.settings.last_project_path)

    def update_theme_style(self):
        """
        Применяет палитру и обновляет CSS стили для конкретных элементов.
        """
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()

        # Определяем цвета для CSS
        if self.settings.dark_mode:
            c_bg = QColor(44, 44, 44)
            c_fg = QColor(240, 240, 240)
            c_base = QColor(30, 30, 30)
            c_hl = QColor(42, 130, 218)

            # Строковые цвета для CSS
            css_text_color = "#f0f0f0"
            css_bg_dark = "#1e1e1e"
            css_border = "#3a3a3a"
            css_hover = "#333333"
            css_select = "#2a82da"

            # Цвета чекбоксов
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
            # Цвета для светлой темы
            css_text_color = "#000000"
            css_bg_dark = "#ffffff"  # Обычный фон
            css_border = "#cccccc"  # Обычный бордюр
            css_hover = ""
            css_select = ""
            css_check_border = ""
            css_check_bg = ""

        app.setPalette(palette)

        # === Формируем CSS стили ===

        # 1. Стили для дерева и редактора
        if self.settings.dark_mode:
            # Важно: для QTreeWidget нужно явно стилизовать indicator (чекбокс),
            # иначе в темной теме он сливается с фоном.
            tree_style = (
                f"QTreeWidget {{ background-color: {css_bg_dark}; color: {css_text_color}; border: 1px solid {css_border}; }}"
                f"QTreeWidget::item:hover {{ background-color: {css_hover}; }}"
                f"QTreeWidget::item:selected {{ background-color: {css_select}; }}"
                # Стилизация чекбоксов (indicators)
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

        # 2. Кнопка темы
        self.btn_theme.setText(
            "☀ Light Mode" if self.settings.dark_mode else "☾ Dark Mode"
        )

        # 3. Хайлайтер
        self.highlighter = PythonHighlighter(
            self.preview.document(), is_dark=self.settings.dark_mode
        )

        # 4. Явный цвет для лейблов статистики
        if hasattr(self, "lbl_char_count"):
            base_stat_style = "font-weight: bold; font-size: 12px;"
            self.lbl_char_count.setStyleSheet(
                f"{base_stat_style} color: {css_text_color};"
            )
            self.lbl_token_count.setStyleSheet(f"{base_stat_style} color: #2a82da;")

    def toggle_theme(self):
        self.settings.dark_mode = not self.settings.dark_mode
        self.settings.save()
        self.update_theme_style()

    def init_ui(self):
        self.setWindowTitle("CodeContext Builder")
        self.resize(1250, 850)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # === LEFT ===
        left_panel = QWidget()
        l_layout = QVBoxLayout(left_panel)
        l_layout.setContentsMargins(5, 5, 5, 5)

        btn_open = QPushButton("Open Project Folder")
        btn_open.clicked.connect(self.open_dir_dialog)
        l_layout.addWidget(btn_open)

        self.cb_ignore = QCheckBox("Hide .gitignore files")
        self.cb_ignore.setChecked(self.settings.hide_ignored_files)
        self.cb_ignore.toggled.connect(self.refresh_tree)
        l_layout.addWidget(self.cb_ignore)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Files")
        self.tree.itemChanged.connect(self.on_item_checked)
        self.tree.currentItemChanged.connect(self.on_current_item_changed)
        l_layout.addWidget(self.tree)

        splitter.addWidget(left_panel)

        # === CENTER ===
        center_panel = QWidget()
        c_layout = QVBoxLayout(center_panel)
        c_layout.setContentsMargins(5, 5, 5, 5)

        preview_controls = QHBoxLayout()
        self.rb_file_view = QRadioButton("Single File Preview")
        self.rb_context_view = QRadioButton("Full Context (XML)")
        self.rb_file_view.setChecked(True)

        self.view_group = QButtonGroup()
        self.view_group.addButton(self.rb_file_view)
        self.view_group.addButton(self.rb_context_view)
        self.view_group.buttonToggled.connect(self.update_preview_content)

        preview_controls.addWidget(self.rb_file_view)
        preview_controls.addWidget(self.rb_context_view)
        preview_controls.addStretch()
        c_layout.addLayout(preview_controls)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        font = QFont("Consolas" if os.name == "nt" else "Menlo", 11)
        self.preview.setFont(font)

        c_layout.addWidget(self.preview)
        splitter.addWidget(center_panel)

        # === RIGHT ===
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(5, 5, 5, 5)

        self.btn_theme = QPushButton("Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        r_layout.addWidget(self.btn_theme)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Raw Code", "Skeleton (Interfaces)"])
        self.combo_mode.currentIndexChanged.connect(self.on_processing_mode_changed)
        r_layout.addWidget(QLabel("Processing Mode:"))
        r_layout.addWidget(self.combo_mode)

        ai_group = QGroupBox("AI Settings")
        form = QFormLayout()
        self.inp_url = QLineEdit(self.settings.openai_base_url)
        self.inp_key = QLineEdit(self.settings.openai_api_key.get_secret_value())
        self.inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_model = QLineEdit(self.settings.model_name)

        form.addRow("URL:", self.inp_url)
        form.addRow("API Key:", self.inp_key)
        form.addRow("Model:", self.inp_model)
        ai_group.setLayout(form)
        r_layout.addWidget(ai_group)

        btn_ai = QPushButton("Generate Docs (via AI)")
        btn_ai.clicked.connect(self.run_ai)
        r_layout.addWidget(btn_ai)

        r_layout.addStretch()

        # === STATS PANEL ===
        stats_group = QGroupBox("Context Stats & Tokenizer")
        stats_layout = QVBoxLayout()

        encodings = TokenCounter.get_available_encodings()

        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(encodings)

        default_enc = "cl100k_base"
        if "o200k_base" in encodings:
            default_enc = "o200k_base"
        elif "cl100k_base" in encodings:
            default_enc = "cl100k_base"

        index = self.combo_encoding.findText(default_enc)
        if index >= 0:
            self.combo_encoding.setCurrentIndex(index)

        self.combo_encoding.currentIndexChanged.connect(self.update_stats_display)

        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel("Encoding:"))
        stats_row.addWidget(self.combo_encoding)
        stats_layout.addLayout(stats_row)

        self.lbl_char_count = QLabel("Chars: 0")
        self.lbl_token_count = QLabel("Tokens: 0")
        self.lbl_token_count.setToolTip("Calculated locally using tiktoken library")

        stats_layout.addWidget(self.lbl_char_count)
        stats_layout.addWidget(self.lbl_token_count)
        stats_group.setLayout(stats_layout)
        r_layout.addWidget(stats_group)
        # ===================

        btn_copy = QPushButton("Copy Context to Clipboard")
        btn_copy.setMinimumHeight(50)
        btn_copy.setStyleSheet(
            "background-color: #2da44e; color: white; font-weight: bold; font-size: 14px;"
        )
        btn_copy.clicked.connect(self.copy_context)
        r_layout.addWidget(btn_copy)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 600, 300])

    def open_dir_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.load_project(path)

    def load_project(self, path):
        self.settings.last_project_path = path
        self.save_current_settings()
        self.setWindowTitle(f"CodeContext - {path}")
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
            f = QTreeWidgetItem(parent, [parts[-1]])
            f.setFlags(f.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            f.setCheckState(0, Qt.CheckState.Unchecked)
            f.setData(0, Qt.ItemDataRole.UserRole, str(n.path))

    def on_processing_mode_changed(self):
        self.update_preview_content()

    def update_preview_content(self):
        full_context = self._generate_full_context(limit_preview=False)
        self.cached_full_context = full_context
        self.update_stats_display()

        if self.rb_file_view.isChecked():
            current = self.tree.currentItem()
            if current:
                self.on_current_item_changed(current, None)
            else:
                self.preview.clear()
        else:
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

        selected_encoding = self.combo_encoding.currentText()
        if not selected_encoding:
            selected_encoding = "cl100k_base"

        token_count = TokenCounter.count(text, selected_encoding)

        self.lbl_char_count.setText(f"Chars: {char_count:,}".replace(",", " "))
        self.lbl_token_count.setText(f"Tokens: {token_count:,}".replace(",", " "))

    def on_current_item_changed(self, current, previous):
        if self.rb_context_view.isChecked():
            return
        if not current:
            self.preview.clear()
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if path and Path(path).is_file():
            self.display_file_preview(Path(path))
        else:
            self.preview.clear()

    def display_file_preview(self, path: Path):
        try:
            if CodeProcessor.is_binary(path):
                self.preview.setText("[Binary File]")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(4000)
            if len(content) == 4000:
                content += "\n\n... (truncated) ..."
            self.preview.setText(content)
        except Exception as e:
            self.preview.setText(f"[Error: {e}]")

    def on_item_checked(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_paths.add(path)
            else:
                self.selected_paths.discard(path)

        self.update_preview_content()

    def _generate_full_context(self, limit_preview=False) -> str:
        if not self.settings.last_project_path or not self.selected_paths:
            return ""

        out = []
        is_skel = self.combo_mode.currentText().startswith("Skeleton")
        root = Path(self.settings.last_project_path)
        sorted_paths = sorted([Path(p) for p in self.selected_paths])

        out.append("# Project Structure")
        for p in sorted_paths:
            try:
                rel_path = p.relative_to(root).as_posix()
                out.append(f"- {rel_path}")
            except ValueError:
                pass
        out.append("")

        out.append("# File Contents")

        total_chars = 0
        LIMIT = 10000

        for p in sorted_paths:
            if limit_preview and total_chars > LIMIT:
                out.append("\n... (preview truncated) ...")
                break

            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name

            content = CodeProcessor.process_file(p, is_skel)

            ext = p.suffix.lower()
            lang = "text"
            if ext in [".py", ".pyw"]:
                lang = "python"
            elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                lang = "javascript"
            elif ext in [".html", ".htm"]:
                lang = "html"
            elif ext in [".css", ".scss"]:
                lang = "css"
            elif ext in [".json"]:
                lang = "json"
            elif ext in [".md", ".markdown"]:
                lang = "markdown"
            elif ext in [".sql"]:
                lang = "sql"
            elif ext in [".xml", ".xaml"]:
                lang = "xml"
            elif ext in [".yaml", ".yml"]:
                lang = "yaml"
            elif ext in [".sh", ".bash"]:
                lang = "bash"

            max_tick_seq = 0
            if "`" in content:
                ticks = re.findall(r"`+", content)
                if ticks:
                    max_tick_seq = max(len(t) for t in ticks)
            fence_len = max(3, max_tick_seq + 1)
            fence = "`" * fence_len

            out.append(f"## File: {rel}")
            out.append(f"{fence}{lang}")
            out.append(content)
            out.append(f"{fence}\n")

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
        text = self.cached_full_context
        if not text:
            text = self._generate_full_context(limit_preview=False)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(
            f"Copied {len(self.selected_paths)} files. ({self.lbl_token_count.text()})"
        )

    def run_ai(self):
        if not self.selected_paths:
            QMessageBox.warning(self, "Warning", "Select files first.")
            return
        self.save_current_settings()

        ctx = (
            self.cached_full_context
            if self.cached_full_context
            else self._generate_full_context(limit_preview=False)
        )

        prompt = (
            "Действуй как Senior Developer.\n"
            "Проанализируй код (XML):\n\n"
            f"{ctx}\n\n"
            "Напиши README на русском с описанием архитектуры и назначения модулей."
        )
        self.statusBar().showMessage("Sending request...")
        self.setEnabled(False)
        self.ai = AIWorker(self.settings, prompt)
        self.ai.result_ready.connect(self.on_ai_success)
        self.ai.error_occurred.connect(self.on_ai_error)
        self.ai.finished.connect(lambda: self.setEnabled(True))
        self.ai.start()

    def on_ai_success(self, text):
        self.statusBar().showMessage("Done.")
        dlg = QDialog(self)
        dlg.setWindowTitle("Result")
        dlg.resize(800, 600)
        l = QVBoxLayout(dlg)
        t = QTextEdit()
        t.setPlainText(text)
        l.addWidget(t)
        if self.settings.dark_mode:
            t.setStyleSheet("background-color: #1e1e1e; color: #f0f0f0;")
        dlg.exec()

    def on_ai_error(self, err):
        self.statusBar().showMessage("Error.")
        QMessageBox.critical(self, "AI Error", f"Failed: {err}")

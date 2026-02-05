from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QTextEdit, QSplitter, QFileDialog, QGroupBox, QCheckBox,
    QComboBox, QLineEdit, QFormLayout, QMessageBox, QDialog, QApplication
)

from src.config import AppSettings
from src.core.processor_logic import CodeProcessor
from src.ui.workers import ScanWorker, AIWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load_from_disk()
        self.current_nodes = {}  # path -> FileNode
        self.selected_paths = set()

        self.init_ui()

        if self.settings.last_project_path:
            self.load_project(self.settings.last_project_path)

    def init_ui(self):
        self.setWindowTitle("CodeContext Builder")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: Tree
        left_panel = QWidget()
        l_layout = QVBoxLayout(left_panel)
        btn_open = QPushButton("Open Project")
        btn_open.clicked.connect(self.open_dir_dialog)
        l_layout.addWidget(btn_open)

        self.cb_ignore = QCheckBox("Respect .gitignore")
        self.cb_ignore.setChecked(self.settings.hide_ignored_files)
        self.cb_ignore.toggled.connect(self.refresh_tree)
        l_layout.addWidget(self.cb_ignore)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Files")
        self.tree.itemChanged.connect(self.on_item_checked)
        self.tree.currentItemChanged.connect(self.on_current_item_changed)
        l_layout.addWidget(self.tree)
        splitter.addWidget(left_panel)

        # Center: Preview
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a file to preview...")
        splitter.addWidget(self.preview)

        # Right: Settings
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)

        # Mode
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Raw Code", "Skeleton"])
        r_layout.addWidget(QLabel("Mode:"))
        r_layout.addWidget(self.combo_mode)

        # AI Config
        ai_group = QGroupBox("AI Settings")
        form = QFormLayout()
        self.inp_url = QLineEdit(self.settings.openai_base_url)
        self.inp_key = QLineEdit(self.settings.openai_api_key.get_secret_value())
        self.inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_model = QLineEdit(self.settings.model_name)

        form.addRow("URL:", self.inp_url)
        form.addRow("Key:", self.inp_key)
        form.addRow("Model:", self.inp_model)
        ai_group.setLayout(form)
        r_layout.addWidget(ai_group)

        btn_ai = QPushButton("Generate Docs")
        btn_ai.clicked.connect(self.run_ai)
        r_layout.addWidget(btn_ai)

        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.setStyleSheet("background-color: #2da44e; color: white; padding: 10px; font-weight: bold;")
        btn_copy.clicked.connect(self.copy_context)
        r_layout.addWidget(btn_copy)

        r_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500, 300])

    def open_dir_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.load_project(path)

    def load_project(self, path):
        self.settings.last_project_path = path
        self.settings.save_to_disk()
        self.setWindowTitle(f"CodeContext - {path}")
        self.refresh_tree()

    def refresh_tree(self):
        path = self.settings.last_project_path
        if not path: return

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
            parent_item = self.tree.invisibleRootItem()

            # Create folder hierarchy
            current_rel = Path("")
            for part in parts[:-1]:
                current_rel = current_rel / part
                str_rel = str(current_rel)
                if str_rel not in dirs:
                    item = QTreeWidgetItem(parent_item, [part])
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    dirs[str_rel] = item
                    parent_item = item
                else:
                    parent_item = dirs[str_rel]

            # Create file item
            f_item = QTreeWidgetItem(parent_item, [parts[-1]])
            f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            f_item.setCheckState(0, Qt.CheckState.Unchecked)
            f_item.setData(0, Qt.ItemDataRole.UserRole, str(n.path))

    # --- ПРЕВЬЮ ЛОГИКА (ИСПРАВЛЕНА) ---
    def on_current_item_changed(self, current, previous):
        if not current:
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if path and Path(path).is_file():
            self.display_preview(Path(path))
        else:
            self.preview.clear()

    def display_preview(self, path: Path):
        """Безопасное чтение файла для превью."""
        try:
            # Проверяем размер, чтобы не читать огромные файлы
            if path.stat().st_size == 0:
                self.preview.setText("[Empty File]")
                return

            if CodeProcessor.is_binary(path):
                self.preview.setText("[Binary File]")
                return

            # Читаем только первые 2000 символов
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(2000)

            if len(content) == 2000:
                content += "\n\n... (preview truncated) ..."

            self.preview.setText(content)
        except Exception as e:
            # repr(e) покажет тип ошибки, а не пустоту, если ошибка странная
            self.preview.setText(f"[Error reading file: {repr(e)}]")

    # --- Checkbox Logic ---
    def on_item_checked(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_paths.add(path)
            else:
                self.selected_paths.discard(path)

    # --- Helper: Generate Context ---
    def _generate_full_context(self) -> str:
        if not self.settings.last_project_path or not self.selected_paths:
            return ""

        out = []
        is_skeleton = self.combo_mode.currentText() == "Skeleton"
        root = Path(self.settings.last_project_path)
        sorted_paths = sorted([Path(p) for p in self.selected_paths])

        # 1. Structure
        out.append("Project Structure:")
        for p in sorted_paths:
            try:
                rel = p.relative_to(root)
                out.append(f"- {rel}")
            except ValueError:
                out.append(f"- {p.name}")
        out.append("\n" + "=" * 30 + "\n")

        # 2. Content
        for p in sorted_paths:
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p.name

            out.append(f"=== FILE: {rel} ===")
            content = CodeProcessor.process_file(p, is_skeleton)
            out.append(content + "\n")

        return "\n".join(out)

    def copy_context(self):
        if not self.selected_paths:
            self.statusBar().showMessage("No files selected!")
            return

        text = self._generate_full_context()
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied {len(self.selected_paths)} files to clipboard.")

    # --- AI ЛОГИКА (ПРОМПТЫ НА РУССКОМ) ---
    def run_ai(self):
        if not self.selected_paths:
            QMessageBox.warning(self, "Warning", "Please select files first.")
            return

        # Save settings
        self.settings.openai_base_url = self.inp_url.text()
        if self.inp_key.text() != "EMPTY":
            self.settings.__dict__['openai_api_key'] = self.settings.openai_api_key.__class__(self.inp_key.text())
        self.settings.model_name = self.inp_model.text()
        self.settings.save_to_disk()

        context_code = self._generate_full_context()

        # Обновленный промпт на русском
        full_user_prompt = (
            "Действуй как опытный старший разработчик и технический писатель.\n"
            "Твоя задача: Проанализировать предоставленный ниже код проекта и написать краткую техническую документацию (README) **на русском языке**.\n\n"
            "Структура ответа:\n"
            "1. **Общее описание**: Что делает этот проект.\n"
            "2. **Архитектура**: Основные модули и их назначение.\n"
            "3. **Ключевые технологии**: Библиотеки и паттерны.\n\n"
            f"Вот код проекта:\n\n{context_code}"
        )

        self.statusBar().showMessage("Sending request to LLM...")
        self.setEnabled(False)

        self.ai_worker = AIWorker(self.settings, full_user_prompt)
        self.ai_worker.result_ready.connect(self.on_ai_success)
        self.ai_worker.error_occurred.connect(self.on_ai_error)
        self.ai_worker.finished.connect(lambda: self.setEnabled(True))
        self.ai_worker.start()

    def on_ai_success(self, text):
        self.statusBar().showMessage("AI generation complete.")
        dlg = QDialog(self)
        dlg.setWindowTitle("Generated Documentation")
        dlg.resize(800, 600)

        layout = QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlainText(text)
        layout.addWidget(editor)

        btn_copy = QPushButton("Copy")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        layout.addWidget(btn_copy)

        dlg.exec()

    def on_ai_error(self, err):
        self.statusBar().showMessage("Error occurred.")
        QMessageBox.critical(self, "AI Error", f"Failed: {err}")
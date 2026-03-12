"""Диалог редактирования шаблонов."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QMessageBox,
    QWidget,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.template_manager import TemplateManager
from src.models.prompt_schemas import TemplateCategory, Template


class TemplateEditorDialog(QDialog):
    """Редактор шаблонов (роли, скиллы, правила, форматы)."""

    def __init__(self, template_manager: TemplateManager, parent=None):
        super().__init__(parent)
        self.tm = template_manager
        self._current_template: Template | None = None
        self.setWindowTitle("Template Editor")
        self.setMinimumSize(800, 600)
        self._init_ui()
        self._load_list()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Левая панель: список
        left = QVBoxLayout()

        self.combo_cat = QComboBox()
        for cat in TemplateCategory:
            self.combo_cat.addItem(cat.value, cat)
        self.combo_cat.currentIndexChanged.connect(self._load_list)
        left.addWidget(self.combo_cat)

        self.lst = QListWidget()
        self.lst.currentRowChanged.connect(self._on_select)
        left.addWidget(self.lst)

        btn_row = QHBoxLayout()
        btn_new = QPushButton("+ New")
        btn_new.clicked.connect(self._new_template)
        btn_row.addWidget(btn_new)
        btn_del = QPushButton("🗑 Delete")
        btn_del.clicked.connect(self._delete_template)
        btn_row.addWidget(btn_del)
        left.addLayout(btn_row)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(250)

        # Правая панель: редактор
        right = QVBoxLayout()

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Name:"))
        self.inp_name = QLineEdit()
        self.inp_name.setReadOnly(True)
        r1.addWidget(self.inp_name)
        right.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Display:"))
        self.inp_display = QLineEdit()
        r2.addWidget(self.inp_display)
        right.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Desc:"))
        self.inp_desc = QLineEdit()
        r3.addWidget(self.inp_desc)
        right.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Tags:"))
        self.inp_tags = QLineEdit()
        self.inp_tags.setPlaceholderText("comma-separated tags")
        r4.addWidget(self.inp_tags)
        right.addLayout(r4)

        right.addWidget(QLabel("Content:"))
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        right.addWidget(self.editor)

        btn_save = QPushButton("💾 Save Template")
        btn_save.clicked.connect(self._save_template)
        right.addWidget(btn_save)

        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 550])
        layout.addWidget(splitter)

    def _load_list(self):
        self.lst.clear()
        cat: TemplateCategory = self.combo_cat.currentData()
        if not cat:
            return
        for t in self.tm.get_by_category(cat):
            item = QListWidgetItem(t.display_name)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.lst.addItem(item)

    def _on_select(self, row):
        item = self.lst.item(row)
        if not item:
            return
        t: Template = item.data(Qt.ItemDataRole.UserRole)
        self._current_template = t
        self.inp_name.setText(t.name)
        self.inp_display.setText(t.display_name)
        self.inp_desc.setText(t.description)
        self.inp_tags.setText(", ".join(t.tags))
        self.editor.setPlainText(t.content)

    def _save_template(self):
        if not self._current_template:
            return
        t = self._current_template
        t.display_name = self.inp_display.text().strip() or t.name
        t.description = self.inp_desc.text().strip()
        t.tags = [x.strip() for x in self.inp_tags.text().split(",") if x.strip()]
        t.content = self.editor.toPlainText()
        self.tm.save_template(t)
        self._load_list()
        QMessageBox.information(self, "Saved", f"Template '{t.name}' saved.")

    def _new_template(self):
        cat: TemplateCategory = self.combo_cat.currentData()
        name, ok = QInputDialog.getText(self, "New Template", "Template name (slug):")
        if ok and name.strip():
            name = name.strip().lower().replace(" ", "-")
            self.tm.create_template(
                category=cat,
                name=name,
                content=f"# {name.replace('-', ' ').title()}\n\nDescribe here...\n",
                display_name=name.replace("-", " ").title(),
            )
            self._load_list()

    def _delete_template(self):
        if not self._current_template:
            return
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete template '{self._current_template.name}'?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.tm.delete_template(
                self._current_template.category.value,
                self._current_template.name,
            )
            self._current_template = None
            self._load_list()
            self.editor.clear()
            self.inp_name.clear()
            self.inp_display.clear()
            self.inp_desc.clear()
            self.inp_tags.clear()

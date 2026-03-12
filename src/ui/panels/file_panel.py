"""Панель файлового дерева с чекбоксами."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QComboBox,
    QFileDialog,
    QLineEdit,
)
from PyQt6.QtCore import pyqtSignal, Qt

from src.core.fs_scanner import FileNode, FsScanner
from src.ui.styles import get_file_tree_qss


class FilePanel(QWidget):
    """Панель выбора файлов проекта."""

    selection_changed = pyqtSignal(list)  # list[Path]
    project_opened = pyqtSignal(str)  # project path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node_map: dict[int, FileNode] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Кнопка открыть проект
        top_bar = QHBoxLayout()
        btn_open = QPushButton("📂 Open Project")
        btn_open.clicked.connect(self._open_project)
        top_bar.addWidget(btn_open)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(32)
        btn_refresh.setToolTip("Refresh file tree")
        btn_refresh.clicked.connect(self._request_refresh)
        top_bar.addWidget(btn_refresh)
        layout.addLayout(top_bar)

        # Путь проекта
        self.lbl_path = QLabel("No project opened")
        self.lbl_path.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_path.setWordWrap(True)
        layout.addWidget(self.lbl_path)

        # Поиск
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter files...")
        self.search_input.textChanged.connect(self._filter_tree)
        layout.addWidget(self.search_input)

        # Режим контекста
        mode_bar = QHBoxLayout()
        mode_bar.addWidget(QLabel("Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["full", "skeleton"])
        self.combo_mode.setToolTip("full = всё содержимое, skeleton = только структура")
        mode_bar.addWidget(self.combo_mode)
        layout.addLayout(mode_bar)

        # Кнопки массового выбора
        sel_bar = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(self._select_all)
        sel_bar.addWidget(btn_all)

        btn_none = QPushButton("Clear")
        btn_none.clicked.connect(self._clear_selection)
        sel_bar.addWidget(btn_none)
        layout.addLayout(sel_bar)

        # Дерево
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(get_file_tree_qss(dark=True))
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

        # Статистика
        self.lbl_stats = QLabel("0 files selected")
        self.lbl_stats.setStyleSheet("font-size: 11px; color: #aaa;")
        layout.addWidget(self.lbl_stats)

    def _open_project(self):
        path = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if path:
            self.project_opened.emit(path)

    def _request_refresh(self):
        path = self.lbl_path.property("project_path")
        if path:
            self.project_opened.emit(path)

    # ─── Tree Building ───

    def populate_tree(self, root_node: FileNode, project_path: str):
        """Заполнить дерево из FileNode."""
        self.lbl_path.setText(project_path)
        self.lbl_path.setProperty("project_path", project_path)
        self.tree.blockSignals(True)
        self.tree.clear()
        self._node_map.clear()

        for child in root_node.children:
            item = self._build_tree_item(child)
            self.tree.addTopLevelItem(item)

        self.tree.expandAll()
        self.tree.blockSignals(False)
        self._update_stats()

    def _build_tree_item(self, node: FileNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem()

        if node.is_dir:
            item.setText(0, f"📁 {node.name}")
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsAutoTristate
            )
            item.setCheckState(0, Qt.CheckState.Unchecked)
            for child in node.children:
                child_item = self._build_tree_item(child)
                item.addChild(child_item)
        else:
            size_kb = node.size / 1024
            suffix = f" ({size_kb:.1f} KB)" if size_kb > 1 else ""
            item.setText(0, f"{node.name}{suffix}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)

        self._node_map[id(item)] = node
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        return item

    # ─── Selection ───

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        self._update_stats()
        self.selection_changed.emit(self.get_selected_paths())

    def get_selected_paths(self) -> list[Path]:
        """Вернуть пути всех выбранных файлов."""
        paths = []
        self._collect_checked(self.tree.invisibleRootItem(), paths)
        return paths

    def _collect_checked(self, parent: QTreeWidgetItem, paths: list[Path]):
        for i in range(parent.childCount()):
            child = parent.child(i)
            node: FileNode | None = child.data(0, Qt.ItemDataRole.UserRole)
            if (
                node
                and not node.is_dir
                and child.checkState(0) == Qt.CheckState.Checked
            ):
                paths.append(node.path)
            self._collect_checked(child, paths)

    def _select_all(self):
        self.tree.blockSignals(True)
        self._set_check_all(self.tree.invisibleRootItem(), Qt.CheckState.Checked)
        self.tree.blockSignals(False)
        self._on_item_changed(None, 0)

    def _clear_selection(self):
        self.tree.blockSignals(True)
        self._set_check_all(self.tree.invisibleRootItem(), Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._on_item_changed(None, 0)

    def _set_check_all(self, parent: QTreeWidgetItem, state: Qt.CheckState):
        for i in range(parent.childCount()):
            child = parent.child(i)
            child.setCheckState(0, state)
            self._set_check_all(child, state)

    def _update_stats(self):
        paths = self.get_selected_paths()
        total_size = sum(p.stat().st_size for p in paths if p.exists())
        size_kb = total_size / 1024
        self.lbl_stats.setText(f"{len(paths)} files selected ({size_kb:.0f} KB)")

    def _filter_tree(self, text: str):
        """Фильтрация дерева по имени файла."""
        text = text.lower().strip()
        self._filter_item(self.tree.invisibleRootItem(), text)

    def _filter_item(self, parent: QTreeWidgetItem, text: str) -> bool:
        any_visible = False
        for i in range(parent.childCount()):
            child = parent.child(i)
            node: FileNode | None = child.data(0, Qt.ItemDataRole.UserRole)

            if not text:
                child.setHidden(False)
                self._filter_item(child, text)
                any_visible = True
                continue

            if node and node.is_dir:
                child_visible = self._filter_item(child, text)
                child.setHidden(not child_visible)
                any_visible = any_visible or child_visible
            else:
                matches = text in (node.name.lower() if node else "")
                child.setHidden(not matches)
                any_visible = any_visible or matches

        return any_visible

    def get_context_mode(self) -> str:
        return self.combo_mode.currentText()

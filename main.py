"""Prompt Workshop — модульный конструктор промптов для LLM-кодинга."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from src.config import ROOT_DIR, ensure_dirs
from src.ui.main_window import MainWindow
from src.ui.styles import get_dark_theme_qss


def main():
    ensure_dirs()

    app = QApplication(sys.argv)
    app.setApplicationName("Prompt Workshop")
    app.setStyle("Fusion")

    # Тёмная тема
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtCore import Qt

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Text, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(212, 212, 212))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(128, 128, 128),
    )
    app.setPalette(palette)

    app.setStyleSheet(
        get_dark_theme_qss()
        + """
        QToolTip { background-color: #2b2b2b; color: #d4d4d4; border: 1px solid #555; padding: 4px; }
        QGroupBox { font-weight: bold; border: 1px solid #555; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QTabWidget::pane { border: 1px solid #555; }
        QTabBar::tab { background: #2b2b2b; padding: 6px 14px; margin-right: 2px; border: 1px solid #555; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background: #3c3c3c; }
        QTabBar::tab:hover { background: #4a4a4a; }
        QPushButton { padding: 5px 12px; border: 1px solid #555; border-radius: 3px; background: #3c3c3c; }
        QPushButton:hover { background: #4a4a4a; }
        QPushButton:pressed { background: #2a2a2a; }
        QPushButton:disabled { color: #666; background: #2b2b2b; }
        QComboBox { padding: 4px 8px; border: 1px solid #555; border-radius: 3px; background: #3c3c3c; }
        QComboBox:hover { border-color: #2a82da; }
        QComboBox QAbstractItemView { background: #2b2b2b; border: 1px solid #555; selection-background-color: #2a82da; }
        QCheckBox { spacing: 6px; }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QPlainTextEdit, QTextEdit { border: 1px solid #555; border-radius: 3px; background: #1e1e1e; }
        QScrollBar:vertical { width: 10px; background: #1e1e1e; }
        QScrollBar::handle:vertical { background: #555; border-radius: 4px; min-height: 20px; }
        QScrollBar::handle:vertical:hover { background: #777; }
        QTreeWidget { border: 1px solid #555; border-radius: 3px; }
        QTreeWidget::item { padding: 2px 0; }
        QTreeWidget::item:hover { background: #3c3c3c; }
        QTreeWidget::item:selected { background: #2a82da; }
        QSplitter::handle { background: #555; }
        QSplitter::handle:horizontal { width: 2px; }
        QSplitter::handle:vertical { height: 2px; }
        QStatusBar { background: #252525; border-top: 1px solid #555; }
        QMenuBar { background: #2b2b2b; border-bottom: 1px solid #555; }
        QMenuBar::item:selected { background: #3c3c3c; }
        QMenu { background: #2b2b2b; border: 1px solid #555; }
        QMenu::item:selected { background: #2a82da; }
    """
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

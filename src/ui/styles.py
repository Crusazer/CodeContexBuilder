"""Централизованный модуль стилей и QSS-констант для тёмной темы."""

from __future__ import annotations

DARK_TREE_INDICATOR_SIZE: int = 18


def get_file_tree_qss(dark: bool = True) -> str:
    """Вернуть QSS для QTreeWidget с контрастными чекбоксами.

    Args:
        dark: использовать тёмную цветовую схему (True) или светлую (False).

    Returns:
        QSS-строка для применения к QTreeWidget.
    """
    if dark:
        return _DARK_TREE_QSS
    return _LIGHT_TREE_QSS


def get_dark_theme_qss() -> str:
    """Вернуть дополнительный глобальный QSS для тёмной темы.

    Содержит стили для чекбокс-индикаторов в QTreeWidget,
    которые плохо различимы со стандартным Fusion-стилем на тёмном фоне.
    """
    return _DARK_GLOBAL_CHECKBOX_QSS


# ── Тёмная тема: стили дерева ──────────────────────────────────────────────

_DARK_TREE_QSS = f"""
QTreeWidget::indicator {{
    width: {DARK_TREE_INDICATOR_SIZE}px;
    height: {DARK_TREE_INDICATOR_SIZE}px;
}}

/* ── unchecked ── */
QTreeWidget::indicator:unchecked {{
    border: 2px solid #aaaaaa;
    border-radius: 3px;
    background: transparent;
}}
QTreeWidget::indicator:unchecked:hover {{
    border: 2px solid #66bbff;
    background: rgba(42, 130, 218, 0.1);
}}

/* ── checked ── */
QTreeWidget::indicator:checked {{
    border: 2px solid #4a9eff;
    border-radius: 3px;
    background: #4a9eff;
}}
QTreeWidget::indicator:checked:hover {{
    border: 2px solid #66bbff;
    background: #66bbff;
}}

/* ── partially checked (indeterminate / tristate) ── */
QTreeWidget::indicator:indeterminate {{
    border: 2px solid #4a9eff;
    border-radius: 3px;
    background: #2a5a8a;
}}
QTreeWidget::indicator:indeterminate:hover {{
    border: 2px solid #66bbff;
    background: #3a6a9a;
}}
"""

# ── Светлая тема: стили дерева ─────────────────────────────────────────────

_LIGHT_TREE_QSS = f"""
QTreeWidget::indicator {{
    width: {DARK_TREE_INDICATOR_SIZE}px;
    height: {DARK_TREE_INDICATOR_SIZE}px;
}}

QTreeWidget::indicator:unchecked {{
    border: 2px solid #888888;
    border-radius: 3px;
    background: #ffffff;
}}
QTreeWidget::indicator:unchecked:hover {{
    border: 2px solid #2a82da;
    background: #e8f0fe;
}}

QTreeWidget::indicator:checked {{
    border: 2px solid #2a82da;
    border-radius: 3px;
    background: #2a82da;
}}
QTreeWidget::indicator:checked:hover {{
    border: 2px solid #1a6fbe;
    background: #1a6fbe;
}}

QTreeWidget::indicator:indeterminate {{
    border: 2px solid #2a82da;
    border-radius: 3px;
    background: #a0c4e8;
}}
QTreeWidget::indicator:indeterminate:hover {{
    border: 2px solid #1a6fbe;
    background: #80b0d8;
}}
"""

# ── Глобальный QSS для чекбоксов (тёмная тема) ────────────────────────────
# Применяется через app.setStyleSheet() поверх остальных стилей,
# чтобы перекрыть дефолтные индикаторы Fusion на тёмном фоне.

_DARK_GLOBAL_CHECKBOX_QSS = f"""
QTreeWidget::indicator {{
    width: {DARK_TREE_INDICATOR_SIZE}px;
    height: {DARK_TREE_INDICATOR_SIZE}px;
}}

QTreeWidget::indicator:unchecked {{
    border: 2px solid #aaaaaa;
    border-radius: 3px;
    background: transparent;
}}
QTreeWidget::indicator:unchecked:hover {{
    border: 2px solid #66bbff;
    background: rgba(42, 130, 218, 0.1);
}}

QTreeWidget::indicator:checked {{
    border: 2px solid #4a9eff;
    border-radius: 3px;
    background: #4a9eff;
}}
QTreeWidget::indicator:checked:hover {{
    border: 2px solid #66bbff;
    background: #66bbff;
}}

QTreeWidget::indicator:indeterminate {{
    border: 2px solid #4a9eff;
    border-radius: 3px;
    background: #2a5a8a;
}}
QTreeWidget::indicator:indeterminate:hover {{
    border: 2px solid #66bbff;
    background: #3a6a9a;
}}
"""

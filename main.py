import sys

from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Настройка стиля
    app.setStyle("Fusion")

    # Не устанавливаем специфичный шрифт, чтобы избежать предупреждений на Mac/Linux.
    # Если нужно увеличить шрифт глобально, можно раскомментировать и использовать общий шрифт:
    # font = app.font()
    # font.setPointSize(10)
    # app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
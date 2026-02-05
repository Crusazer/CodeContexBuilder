from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.config import AppSettings
from src.core.ai_service import AIService  # (см. ниже)
from src.core.fs_scanner import ProjectScanner


class ScanWorker(QThread):
    finished = pyqtSignal(list)  # List[FileNode]

    def __init__(self, path: str, respect_gitignore: bool):
        super().__init__()
        self.path = Path(path)
        self.respect_gitignore = respect_gitignore

    def run(self):
        scanner = ProjectScanner(self.path, self.respect_gitignore)
        nodes = scanner.scan()
        self.finished.emit(nodes)


class AIWorker(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, settings: AppSettings, prompt: str):
        super().__init__()
        self.settings = settings
        self.prompt = prompt

    def run(self):
        try:
            service = AIService(self.settings)
            result = service.generate_docs(self.prompt)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

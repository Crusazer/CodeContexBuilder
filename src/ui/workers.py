from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex

from src.config import AppSettings
from src.core.ai_service import AIService, AgentService
from src.core.fs_scanner import ProjectScanner


class ScanWorker(QThread):
    finished = pyqtSignal(list)

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


class AgentWorker(QThread):
    """
    Воркер для запуска агента.
    """

    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    # Сигнал запроса подтверждения СОЗДАНИЯ: (path, content)
    request_creation_signal = pyqtSignal(str, str)

    # Сигнал запроса подтверждения РЕДАКТИРОВАНИЯ: (path, original, new)
    request_edit_signal = pyqtSignal(str, str, str)

    def __init__(
        self,
        settings: AppSettings,
        project_root: Path,
        context: str,
        user_prompt: str,
        use_reasoning: bool,
    ):
        super().__init__()
        self.settings = settings
        self.project_root = project_root
        self.context = context
        self.user_prompt = user_prompt
        self.use_reasoning = use_reasoning

        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.user_approved_last_action = False

    def set_user_response(self, approved: bool):
        """Передача ответа от UI."""
        self.mutex.lock()
        self.user_approved_last_action = approved
        self.condition.wakeAll()
        self.mutex.unlock()

    def _file_creation_callback(self, rel_path: str, content: str) -> bool:
        """Обработка создания файла."""
        self.request_creation_signal.emit(rel_path, content)

        # Ждем ответа
        self.mutex.lock()
        self.condition.wait(self.mutex)
        approved = self.user_approved_last_action
        self.mutex.unlock()

        if approved:
            try:
                full_path = self.project_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.log_signal.emit(f"[System] File created: {rel_path}")
                return True
            except Exception as e:
                self.log_signal.emit(f"[System] Error writing file: {e}")
                return False
        else:
            self.log_signal.emit(f"[System] File creation denied by user: {rel_path}")
            return False

    def _file_editor_callback(self, rel_path: str, original: str, new_code: str) -> str:
        """Обработка редактирования файла."""
        full_path = self.project_root / rel_path

        # 1. Проверяем, существует ли файл
        if not full_path.exists():
            return f"Error: File {rel_path} does not exist. Use create_file instead."

        # 2. Читаем файл
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        # 3. Проверяем вхождение original_snippet
        count = file_content.count(original)
        if count == 0:
            return "Error: `original_snippet` not found in the file. Check whitespace and indentation exactly."
        if count > 1:
            return "Error: `original_snippet` occurs multiple times. Provide more context to make it unique."

        # 4. Спрашиваем пользователя
        self.request_edit_signal.emit(rel_path, original, new_code)

        self.mutex.lock()
        self.condition.wait(self.mutex)
        approved = self.user_approved_last_action
        self.mutex.unlock()

        # 5. Применяем изменения
        if approved:
            try:
                new_file_content = file_content.replace(original, new_code)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_file_content)
                self.log_signal.emit(f"[System] File edited: {rel_path}")
                return "Success: File edited."
            except Exception as e:
                self.log_signal.emit(f"[System] Error writing file: {e}")
                return f"Error writing file: {e}"
        else:
            self.log_signal.emit(f"[System] Edit denied by user: {rel_path}")
            return "User denied the edit."

    def run(self):
        try:
            agent = AgentService(self.settings)
            result = agent.run_agent_loop(
                context=self.context,
                user_prompt=self.user_prompt,
                use_reasoning=self.use_reasoning,
                file_creator_callback=self._file_creation_callback,
                file_editor_callback=self._file_editor_callback,  # Передаем новый коллбек
                log_callback=lambda msg: self.log_signal.emit(msg),
            )
            self.result_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))

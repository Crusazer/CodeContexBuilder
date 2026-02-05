from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex

from src.config import AppSettings
from src.core.ai_service import AIService, AgentService  # Обновлен импорт
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
    Поддерживает Human-in-the-loop через сигналы и блокировку потока.
    """

    log_signal = pyqtSignal(str)  # Логи процесса
    result_signal = pyqtSignal(str)  # Финальный результат
    error_signal = pyqtSignal(str)  # Ошибка

    # Сигнал запроса подтверждения: (path, content)
    request_approval_signal = pyqtSignal(str, str)

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

        # Механизмы синхронизации
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.user_approved_last_action = False

    def set_user_response(self, approved: bool):
        """Вызывается из UI потока, чтобы передать ответ пользователя."""
        self.mutex.lock()
        self.user_approved_last_action = approved
        self.condition.wakeAll()
        self.mutex.unlock()

    def _file_creation_callback(self, rel_path: str, content: str) -> bool:
        """
        Этот метод вызывается внутри run_agent_loop (в этом потоке).
        Он должен:
        1. Отправить сигнал в UI.
        2. Заблокировать выполнение, пока UI не ответит.
        3. Если Approve -> Создать файл.
        4. Вернуть True/False.
        """

        # 1. Отправляем запрос
        self.request_approval_signal.emit(rel_path, content)

        # 2. Ждем ответа
        self.mutex.lock()
        self.condition.wait(self.mutex)
        approved = self.user_approved_last_action
        self.mutex.unlock()

        # 3. Действуем
        if approved:
            try:
                full_path = self.project_root / rel_path
                # Создаем директории если нет
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

    def run(self):
        try:
            agent = AgentService(self.settings)
            result = agent.run_agent_loop(
                context=self.context,
                user_prompt=self.user_prompt,
                use_reasoning=self.use_reasoning,
                file_creator_callback=self._file_creation_callback,
                log_callback=lambda msg: self.log_signal.emit(msg),
            )
            self.result_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))

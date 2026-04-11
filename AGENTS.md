# AGENTS.md

## 1. Обзор проекта

**Prompt Workshop** — десктопное приложение (Python + PyQt6) для модульной сборки промптов к LLM-моделям в контексте существующих проектов. Основной workflow: собрать промпт из переиспользуемых блоков → скопировать в Claude/GPT → получить ответ в формате SEARCH/REPLACE → применить диффы к проекту. Также доступен агентский режим (`AgentService`) с tool-calling.

**Стек:** Python 3.13+, PyQt6, Pydantic v2, pydantic-settings, tiktoken, openai, pathspec

**Точка входа:** `main.py` → `ensure_dirs()` → `QApplication` (Fusion + тёмная палитра) → `MainWindow`.

---

## 2. Архитектура

```
main.py                          # Точка входа, тёмная тема, QSS
src/
├── config.py                    # Пути, настройки, JSON-пресистенс
├── controller.py                # AppController — медиатор UI ↔ Core
├── core/
│   ├── ai_service.py            # OpenAI-клиент + агентский цикл (tool-calling)
│   ├── diff_engine.py           # Парсинг и применение SEARCH/REPLACE блоков
│   ├── fs_scanner.py            # Сканер ФС → дерево FileNode
│   ├── git_service.py           # Git: изменённые/нетрекнутые файлы
│   ├── parser_logic.py          # ContextBuilder: файлы → текстовый контекст
│   ├── processor_logic.py       # AST-скелетонизация Python-файлов
│   ├── prompt_builder.py        # Сборка промпта из модулей
│   ├── template_manager.py      # CRUD шаблонов (.md + YAML frontmatter)
│   ├── token_counter.py         # Подсчёт токенов (tiktoken / оценка)
│   └── workflow_engine.py       # Многошаговые воркфлоу (persist в JSON)
├── models/
│   ├── prompt_schemas.py        # Template, PromptAssembly, TemplateCategory
│   ├── schemas.py               # FileNode, PromptContext
│   └── workflow_schemas.py      # Workflow, WorkflowStep, StepStatus, builtin
└── ui/
    ├── main_window.py           # MainWindow — оркестратор всех панелей
    ├── styles.py                # QSS: тёмная/светлая тема для чекбоксов дерева
    ├── workers.py               # QThread-воркеры (скан, AI, агент)
    ├── dialogs/
    │   └── template_editor_dialog.py   # Диалог CRUD шаблонов
    └── panels/
        ├── file_panel.py               # Дерево файлов + чекбоксы + фильтр
        ├── prompt_builder_panel.py     # UI выбора role/skills/rules/format
        ├── task_panel.py               # Поле задачи + ответ модели + diff-кнопки
        └── workflow_panel.py           # UI воркфлоу: шаги, навигация
```

### Слойная модель

| Слой | Ответственность | Правило |
|------|----------------|---------|
| **`models/`** | Pydantic-схемы данных | Без логики (кроме `PromptAssembly.assembled_prompt`) |
| **`core/`** | Бизнес-логика | Не знает о Qt. Не импортирует `src.ui` |
| **`controller.py`** | Единственная точка связи UI ↔ Core | Хранит состояние (project_root, selected_files, context_mode) |
| **`ui/`** | PyQt6-виджеты | Сигналы → вызовы контроллера → обновление UI. НИКОГДА не вызывает core напрямую |

---

## 3. Поток данных

```
1. Open Project
   FsScanner.scan() → FileNode-дерево → FilePanel.populate_tree()

2. Select Files (чекбоксы / git-changed / фильтр)
   FilePanel.selection_changed → controller.set_selected_files()
   → ContextBuilder.build_context() → file_preview

3. Configure Prompt
   PromptBuilderPanel → controller._sync_builder_from_panel()
   → PromptBuilder.set_role / add_skill / add_rule / set_output_format

4. Write Task
   TaskPanel.task_changed → controller.assemble_prompt(task, extra)
   → PromptAssembly.assembled_prompt → assembled_preview

5. Copy to Clipboard
   TaskPanel.copy_requested → clipboard.setText(prompt)

6. Parse & Apply Diffs
   TaskPanel.parse_diffs_requested → DiffEngine.parse() → DiffBlock[]
   → DiffEngine.dry_run() → preview в Diff Preview tab
   → DiffEngine.apply_all() → .bak-бэкапы → запись файлов → refresh дерева

7. Agent Mode (опционально)
   AgentWorker → AgentService.run_agent_loop()
   → tool-calling: create_file / edit_file / reasoning / final_answer
   → UI-подтверждение через QMutex/QWaitCondition
```

---

## 4. Ключевые концепции

### Шаблоны (Templates)

Хранятся в `templates/{category}/*.md` с YAML frontmatter:

```markdown
---
display_name: "Worker"
description: "Исполнитель кода"
tags: [coding, implementation]
---
# Worker
You are a code implementation specialist...
```

**Категории** (`TemplateCategory`): `roles`, `skills`, `rules`, `output_formats`.

Загружаются `TemplateManager` при старте, кешируются в `_cache` по ключу `"{category}/{name}"`. Парсинг frontmatter — ручной fallback (python-frontmatter НЕ в зависимостях).

### Сборка промпта (`PromptAssembly`)

Визуальный формат финального промпта:

```
============================================================
# ROLE
============================================================

(содержимое шаблона роли)

============================================================
# TECHNICAL CONTEXT & SKILLS
============================================================

## Skill Name

(содержимое скилла)

============================================================
# RULES & CONSTRAINTS
============================================================

## Rule Name

(содержимое правила)

============================================================
# OUTPUT FORMAT
============================================================

(шаблон формата вывода)

============================================================
# INSTRUCTIONS FROM PREVIOUS STEP
============================================================

(результаты предыдущего шага воркфлоу)

============================================================
# PROJECT CODE
============================================================

## File: src/foo.py
```python
...
```

============================================================
# TASK
============================================================

(текст задачи пользователя)
```

**Важно:** `assembled_prompt` — property, пересчитывается при каждом обращении, не кешируется. Порядок секций фиксирован.

### Формат диффов (`DiffEngine`) — ⚠️ КРИТИЧЕСКИЙ КОНТРАКТ

Модель ДОЛЖНА отвечать строго в этом формате:

```markdown
## File: path/to/file.py
<<<<<<< SEARCH
exact original code including whitespace
=======
new replacement code
>>>>>>> REPLACE
```

Правила:
1. `SEARCH` должен встречаться в файле **ровно 1 раз**, иначе ошибка «ambiguous»
2. Пустой `SEARCH` → создание нового файла (`is_new_file=True`)
3. `apply_all()` создаёт `.bak`-копии перед изменением
4. Всегда вызывай `dry_run()` перед `apply_all()`
5. Fallback: нормализация trailing whitespace при отсутствии точного совпадения

### Воркфлоу (`WorkflowEngine`)

3 встроенных сценария (`BUILTIN_WORKFLOWS`):
- **`new-feature`** (4 шага): Orchestrator → Architect → Worker ��� Reviewer
- **`bug-fix`** (1 шаг): Debugger
- **`refactor`** (2 шага): Architect → Worker

Каждый шаг (`WorkflowStep`) задаёт: роль, скиллы, правила, формат, `context_mode`. При `advance_step(result_text)` результат подставляется в секцию `INSTRUCTIONS FROM PREVIOUS STEP`. Воркспейсы персистятся в `workspaces/*.json`.

### Агентский режим (`AgentService`)

Tool-calling цикл с инструментами:
- `reasoning` — план (если `use_reasoning=True`)
- `create_file(path, content)` — создание файла (с подтверждением UI)
- `edit_file(path, original_snippet, new_snippet)` — редактирование (с подтверждением UI)
- `final_answer(summary)` — завершение

Максимум 15 шагов. UI-подтверждение через `QMutex`/`QWaitCondition` в `AgentWorker`.

### Контекст файлов (`ContextBuilder`)

- `mode='full'` — весь файл (до 512 KB)
- `mode='skeleton'` — для `.py`: только imports, classes, defs, docstrings, декораторы, константы (через построчный парсинг). Для остальных: первые 50 строк.

---

## 5. Конвенции кода

| Аспект | Правило |
|--------|---------|
| Язык комментариев/докстрингов | Русский |
| Функции/переменные | `snake_case` |
| Классы | `PascalCase` |
| Модели данных | Pydantic `BaseModel`, `Field(default_factory=list)` |
| Сигналы PyQt | `pyqtSignal` с конкретными типами |
| Логирование | `logging.getLogger(__name__)` |
| Пути | `pathlib.Path` везде, не `os.path` |
| Кодировка | UTF-8 явно: `read_text(encoding="utf-8")` |
| Иммутабельность | `Config.frozen = False` (модели мутируются) |
| Тема UI | Fusion + тёмная палитра, QSS в `main.py` и `styles.py` |

---

## 6. Зависимости

| Пакет | Назначение | Обязательность |
|-------|-----------|----------------|
| `PyQt6` | UI-фреймворк | Да |
| `pydantic` | Модели данных | Да |
| `pydantic-settings` | Настройки (AppSettings) | Да |
| `openai` | AI/Agent API | Да |
| `tiktoken` | Точный подсчёт токенов (`cl100k_base`) | Да |
| `pathspec` | Gitignore-совместимые паттерны | Да |
| `python-frontmatter` | Парсинг YAML frontmatter | Нет (ручной fallback в `TemplateManager`) |

---

## 7. Внешние ресурсы

```
project_root/
├── main.py                    # Точка входа
├── pyproject.toml             # Зависимости
├── settings.json              # last_project_path, theme, recent_projects
├── templates/
│   ├── roles/*.md
│   ├── skills/*.md
│   ├── rules/*.md
│   └── output_formats/*.md
└── workspaces/*.json          # Сохранённые воркфлоу-сессии
```

`settings.json` — читается/пишется через `load_settings()`/`save_settings()` из `config.py`. При отсутствии — дефолт с `theme: "dark"`, `default_context_mode: "full"`, `token_warning_threshold: 100000`.

---

## 8. Подводные камни

- **`PromptAssembly.assembled_prompt`** — property, пересчитывается при каждом обращении. Не кешируется. Не вызывай в цикле без необходимости.
- **`controller._sync_builder_from_panel()`** — мутирует `_assembly.skills` / `_assembly.rules` через `.clear()` напрямую, обходя API `PromptBuilder`. Если вызвать `add_skill()` до `_sync_builder_from_panel()`, результат затрётся.
- **`DiffEngine.apply_block`** — при нормализации whitespace использует подсчёт строк, что может дать неточный результат при смешанных пробелах/табах.
- **`AgentWorker`** — блокирует воркер-поток через `QWaitCondition.wait()`. UI-поток не блокируется, но воркер ждёт ответа пользователя бесконечно.
- **`GitService`** — вызывает `git` через `subprocess`, требует git в PATH. Таймаут — 10 сек. Не работает без git.
- **`FsScanner`** — игнорирует директории по glob-паттернам (`DEFAULT_IGNORE`), НЕ читает `.gitignore`. `pathspec` в зависимостях, но не используется в сканере.
- **`src/core/ai_service.py`** импортирует `src.config.AppSettings` — этот класс нигде не определён. Нужно создать (pydantic-settings `BaseSettings` с полями `openai_api_key`, `openai_base_url`, `model_name`).
- **`src/core/workers.py`** импортирует `src.core.fs_scanner.ProjectScanner` — этот класс не существует. Используется `FsScanner`. Вероятно, артефакт рефакторинга.
- **`src/core/processor_logic.py`** (`SkeletonTransformer`) — не используется нигде в проекте. Skeleton-режим реализован в `parser_logic.py._make_skeleton()` через построчный парсинг, не через AST.

---

## 9. Частые задачи для агента

### «Добавить новую роль/скилл/правило»
1. Создать `templates/{category}/name.md` с frontmatter
2. Перегрузить через меню Templates → Reload (или `TemplateManager.reload()`)
3. Код менять не нужно — автоматически появится в PromptBuilderPanel

### «Добавить новый воркфлоу»
→ Править `BUILTIN_WORKFLOWS` в `src/models/workflow_schemas.py`. Не трогать `workflow_engine.py`.

### «Починить парсинг диффов»
→ `src/core/diff_engine.py`, метод `parse()`. Регекс `PATTERN` — источник истины.

### «Добавить skeleton для TypeScript»
→ `src/core/parser_logic.py`, `_make_skeleton()`. Сейчас работает только для `.py`. Добавить ветку для `.ts`/`.tsx`.

### «Git не находит изменения»
→ `src/core/git_service.py`, `_run_git_command()`. Проверить `is_git_repo()`, таймаут 10 сек.

### «Новый AI-провайдер»
→ Унаследовать `AIService`, переопределить `generate_docs()` / `run_agent_loop()`.

### «Новый tool для агента»
→ Добавить определение в `src/core/ai_service.py` (словарь `TOOL_*`), добавить в список `tools` в `run_agent_loop()`, добавить обработку в `elif fn_name == ...`.

---

## 10. Чего НЕ делать

- ❌ Не менять структуру секций в `PromptAssembly.assembled_prompt` — от неё зависит UI и парсинг
- ❌ Не убирать `.bak` бэкапы в `DiffEngine.apply_all()`
- ❌ Не хардкодить пути — использовать `config.TEMPLATES_DIR`, `config.WORKSPACES_DIR`
- ❌ Не вызывать OpenAI напрямую из UI — только через `AIService` / `AgentService`
- ❌ Не менять формат SEARCH/REPLACE без обновления `DiffEngine.PATTERN`
- ❌ Не добавлять `python-frontmatter` как обязательную зависимость — есть ручной fallback
- ❌ Не блокировать UI-поток AI-вызовами — использовать `AgentWorker` / `AIWorker` (QThread)
- ❌ Не вызывать core-сервисы из UI напрямую — всегда через `AppController`

---

## 11. Точки расширения

| Что | Где | Как |
|-----|-----|-----|
| Новый шаблон | `templates/{category}/*.md` | Создать файл, перезагрузить |
| Новый воркфлоу | `workflow_schemas.py` → `BUILTIN_WORKFLOWS` | Добавить `Workflow` |
| Новый формат диффов | `diff_engine.py` → `PATTERN`, `parse()` | Расширить регекс |
| Новый AI-провайдер | `ai_service.py` → наследование `AIService` | Переопределить методы |
| Новая панель UI | `ui/panels/` | Создать виджет, подключить сигналы в `MainWindow._connect_signals()` |
| Новый tool агента | `ai_service.py` → `TOOL_*` + `run_agent_loop()` | Добавить словарь + ветку обработки |
| Новые ignore-паттерны | `fs_scanner.py` → `DEFAULT_IGNORE` | Добавить в множество |
| Подсчёт токенов для других моделей | `token_counter.py` → `count(encoding=...)` | Передать другой encoding |
| Поддержка `.gitignore` | `fs_scanner.py` | Использовать `pathspec` (уже в зависимостях) |
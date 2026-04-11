# DEPS.md
# Format: module → internal dependencies
# ⚠️ = references symbol not defined in project
# AI: update this file when imports change

main.py → src.config, src.ui.main_window, src.ui.styles

src/config.py → ∅

src/controller.py → src.config, src.core.diff_engine, src.core.fs_scanner, src.core.git_service, src.core.parser_logic, src.core.prompt_builder, src.core.template_manager, src.core.token_counter, src.core.workflow_engine, src.models.workflow_schemas

src/core/ai_service.py → src.config ⚠️AppSettings
src/core/diff_engine.py → ∅
src/core/fs_scanner.py → ∅
src/core/git_service.py → ∅
src/core/parser_logic.py → src.core.fs_scanner
src/core/processor_logic.py → ∅
src/core/prompt_builder.py → src.core.template_manager, src.core.token_counter, src.models.prompt_schemas
src/core/template_manager.py → src.models.prompt_schemas
src/core/token_counter.py → ∅
src/core/workflow_engine.py → src.models.workflow_schemas

src/models/prompt_schemas.py → src.core.token_counter
src/models/schemas.py → ∅
src/models/workflow_schemas.py → ∅

src/ui/main_window.py → src.controller, src.ui.panels.file_panel, src.ui.panels.prompt_builder_panel, src.ui.panels.task_panel, src.ui.panels.workflow_panel
src/ui/styles.py → ∅
src/ui/workers.py → src.config ⚠️AppSettings, src.core.ai_service ⚠️ProjectScanner
src/ui/dialogs/template_editor_dialog.py → src.core.template_manager, src.models.prompt_schemas
src/ui/panels/file_panel.py → src.core.fs_scanner, src.ui.styles
src/ui/panels/prompt_builder_panel.py → src.core.template_manager, src.core.token_counter, src.models.prompt_schemas
src/ui/panels/task_panel.py → ∅
src/ui/panels/workflow_panel.py → src.models.workflow_schemas
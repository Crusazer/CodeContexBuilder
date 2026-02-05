import json
from typing import Callable, Optional

import openai
from src.config import AppSettings

# --- Tool Definitions ---

TOOL_REASONING = {
    "type": "function",
    "function": {
        "name": "reasoning",
        "description": "Output a step-by-step plan or reasoning before taking actions.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "string",
                    "description": "The detailed plan or reasoning steps.",
                }
            },
            "required": ["plan"],
        },
    },
}

TOOL_CREATE_FILE = {
    "type": "function",
    "function": {
        "name": "create_file",
        "description": "Create a new file with the specified content. Requires user approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file (e.g., src/utils.py).",
                },
                "content": {
                    "type": "string",
                    "description": "The full content of the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
}

# --- НОВЫЙ ИНСТРУМЕНТ ---
TOOL_EDIT_FILE = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Replace a specific part of an existing file. Use this for modifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the existing file.",
                },
                "original_snippet": {
                    "type": "string",
                    "description": "The EXACT text content to be replaced. Must match the file content character-by-character (including indentation).",
                },
                "new_snippet": {
                    "type": "string",
                    "description": "The new text content to replace the original snippet with.",
                },
            },
            "required": ["path", "original_snippet", "new_snippet"],
        },
    },
}

TOOL_FINAL_ANSWER = {
    "type": "function",
    "function": {
        "name": "final_answer",
        "description": "Return the final response to the user indicating the task is complete.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was done.",
                }
            },
            "required": ["summary"],
        },
    },
}


class AIService:
    def __init__(self, settings: AppSettings):
        self.client = openai.Client(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
        )
        self.model = settings.model_name

    def generate_docs(self, prompt: str) -> str:
        """Legacy method for simple generation."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful technical writer."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
        )
        return response.choices[0].message.content


class AgentService(AIService):
    """
    Расширенный сервис для работы в режиме агента.
    """

    def run_agent_loop(
        self,
        context: str,
        user_prompt: str,
        use_reasoning: bool,
        file_creator_callback: Callable[[str, str], bool],
        file_editor_callback: Callable[[str, str, str], str],  # НОВЫЙ КОЛЛБЕК
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Основной цикл агента.
        :param file_editor_callback: Функция (path, old, new) -> str (Результат операции: "Success" или Ошибка).
        """

        system_prompt = (
            "You are an autonomous AI coding agent. "
            "You have access to a specific set of project files (provided in context). "
            "You cannot read files outside of this context. "
            "You can CREATE files using `create_file` and EDIT files using `edit_file`.\n"
            "Process:\n"
        )

        if use_reasoning:
            system_prompt += (
                "1. You MUST first call the `reasoning` tool to outline your plan.\n"
            )
        else:
            system_prompt += "1. Analyze the request.\n"

        system_prompt += (
            "2. Execute necessary actions (create_file, edit_file).\n"
            "   IMPORTANT for `edit_file`: The `original_snippet` must be an EXACT COPY of the code in the file, "
            "including indentation and whitespace. It must be unique within the file.\n"
            "3. When finished, you MUST call the `final_answer` tool."
        )

        full_user_message = f"Project Context:\n{context}\n\nUser Task:\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_message},
        ]

        # Добавляем новый инструмент
        tools = [TOOL_CREATE_FILE, TOOL_EDIT_FILE, TOOL_FINAL_ANSWER]
        if use_reasoning:
            tools.insert(0, TOOL_REASONING)

        max_steps = 15  # Увеличим лимит шагов
        step = 0

        while step < max_steps:
            step += 1
            if log_callback:
                log_callback(f"--- Step {step} (Waiting for LLM) ---")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="required",
                    temperature=0.1,
                )
            except Exception as e:
                return f"API Error: {e}"

            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                if log_callback:
                    log_callback(f"Model response (No Tool): {msg.content}")
                if step == max_steps - 1:
                    return msg.content or "Finished without final answer."
                continue

            # Обработка инструментов
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                args_str = tool_call.function.arguments

                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    self._append_tool_result(
                        messages,
                        tool_call.id,
                        fn_name,
                        "Error: Invalid JSON arguments.",
                    )
                    continue

                if log_callback:
                    log_callback(f"Tool Call: {fn_name}")

                if fn_name == "final_answer":
                    return args.get("summary", "Task Completed.")

                elif fn_name == "reasoning":
                    plan = args.get("plan", "")
                    if log_callback:
                        log_callback(f"Reasoning Plan:\n{plan}")
                    self._append_tool_result(
                        messages, tool_call.id, fn_name, "Plan accepted. Proceed."
                    )

                elif fn_name == "create_file":
                    path = args.get("path")
                    content = args.get("content")
                    if log_callback:
                        log_callback(f"Request to create file: {path}")

                    approved = file_creator_callback(path, content)
                    result_msg = (
                        "File created successfully."
                        if approved
                        else "User denied file creation."
                    )

                    if log_callback:
                        log_callback(f"Result: {result_msg}")
                    self._append_tool_result(
                        messages, tool_call.id, fn_name, result_msg
                    )

                # --- ОБРАБОТКА EDIT_FILE ---
                elif fn_name == "edit_file":
                    path = args.get("path")
                    original = args.get("original_snippet")
                    new_code = args.get("new_snippet")

                    if log_callback:
                        log_callback(f"Request to edit file: {path}")

                    # Вызываем коллбек редактирования
                    result_msg = file_editor_callback(path, original, new_code)

                    if log_callback:
                        log_callback(f"Edit Result: {result_msg}")

                    self._append_tool_result(
                        messages, tool_call.id, fn_name, result_msg
                    )
                # ---------------------------

                else:
                    self._append_tool_result(
                        messages, tool_call.id, fn_name, "Unknown tool."
                    )

        return "Max steps reached without final answer."

    def _append_tool_result(self, messages, tool_call_id, fn_name, content):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": fn_name,
                "content": str(content),
            }
        )

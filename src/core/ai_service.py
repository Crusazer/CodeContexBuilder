import json
from typing import Callable, Optional

import openai
from src.config import AppSettings

# --- Tool Definitions ---

TOOL_REASONING = {
    "type": "function",
    "function": {
        "name": "reasoning",
        "description": "Output a step-by-step plan or reasoning before taking actions. Use this first if Reasoning Mode is enabled.",
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
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Основной цикл агента.
        :param context: Полный контекст файлов (код/скелет).
        :param user_prompt: Запрос пользователя.
        :param use_reasoning: Требовать ли вызов reasoning.
        :param file_creator_callback: Функция (path, content) -> bool (Approved?).
        :param log_callback: Функция для логирования шагов.
        :return: Итоговый ответ.
        """

        system_prompt = (
            "You are an autonomous AI coding agent. "
            "You have access to a specific set of project files (provided in context). "
            "You cannot read files outside of this context. "
            "You can CREATE files using the `create_file` tool.\n"
            "Process:\n"
        )

        if use_reasoning:
            system_prompt += (
                "1. You MUST first call the `reasoning` tool to outline your plan.\n"
            )
        else:
            system_prompt += "1. Analyze the request.\n"

        system_prompt += (
            "2. Execute necessary actions (create_file).\n"
            "3. When finished, you MUST call the `final_answer` tool."
        )

        full_user_message = f"Project Context:\n{context}\n\nUser Task:\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_message},
        ]

        tools = [TOOL_CREATE_FILE, TOOL_FINAL_ANSWER]
        if use_reasoning:
            tools.insert(0, TOOL_REASONING)

        max_steps = 10
        step = 0

        while step < max_steps:
            step += 1
            if log_callback:
                log_callback(f"--- Step {step} (Waiting for LLM) ---")

            try:
                # Force tool usage if strictly needed, but 'auto' is usually usually okay
                # if the system prompt is strong.
                # Some local models support tool_choice="required".
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1,  # Low temp for agents
                )
            except Exception as e:
                return f"API Error: {e}"

            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                # Если модель не вызвала инструмент, а написала текст
                if log_callback:
                    log_callback(f"Model response (No Tool): {msg.content}")

                # Если модель решила просто поболтать, добавляем это в историю и продолжаем,
                # но напоми��аем использовать Final Answer.
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
                    result_content = "Error: Invalid JSON arguments."
                    self._append_tool_result(
                        messages, tool_call.id, fn_name, result_content
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
                    # Возвращаем "OK", чтобы агент продолжил выполнение
                    self._append_tool_result(
                        messages, tool_call.id, fn_name, "Plan accepted. Proceed."
                    )

                elif fn_name == "create_file":
                    path = args.get("path")
                    content = args.get("content")

                    if log_callback:
                        log_callback(f"Request to create file: {path}")

                    # HUMAN IN LOOP
                    approved = file_creator_callback(path, content)

                    if approved:
                        try:
                            # Фактическое создание файла происходит здесь (или можно в callback, но лучше здесь для обработки ошибок)
                            # Но так как callback возвращает bool, нам нужно знать корневой путь?
                            # Агент работает с путями. Передадим ответственность за запись в callback?
                            # Нет, callback только "Approve". Запись делаем тут, но нам нужен root.
                            # Упростим: callback делает запись если Approve, или возвращает False.
                            # НО: `file_creator_callback` в `run_agent_loop` не имеет доступа к `root`?
                            # Сделаем так: callback делает все (диалог + запись). Возвращает результат строкой.

                            # Поправка логики: callback в worker'е. Worker имеет доступ к ФС? Нет.
                            # Callback будет делать emit сигнала UI, UI показывает диалог, worker пишет файл.

                            # Проще: callback возвращает "File created successfully" или "User denied creation".
                            result_msg = "File created successfully."
                        except Exception as e:
                            result_msg = f"Error creating file: {e}"
                    else:
                        result_msg = "User denied file creation."

                    if log_callback:
                        log_callback(f"Result: {result_msg}")

                    self._append_tool_result(
                        messages, tool_call.id, fn_name, result_msg
                    )

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
                "content": content,
            }
        )

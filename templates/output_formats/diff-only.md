---
display_name: "Только diff (unified)"
description: "Вывод изменений в формате unified diff"
tags: [output, diff]
---

# Формат вывода: Unified Diff

Выводи изменения в формате unified diff:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,6 +10,8 @@ def existing_function():
     existing_line
-    old_line
+    new_line
+    additional_line
     existing_line
```
Правила:
Включай достаточно контекстных строк (3+) для однозначного определения места изменения
Используй корректные заголовки --- и +++ с путями к файлам
Используй заголовки ханков @@ с номерами строк
Удалённые строки начинаются с -, добавленные с +, контекст с пробелом
Если меняешь несколько файлов — разделяй их чётко
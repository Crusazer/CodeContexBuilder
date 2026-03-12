---
display_name: "Full File Output"
description: "Output complete file contents"
tags: [output]
---

# Output Format: Full File

For each modified or new file, output the COMPLETE file content.

Format:

## File: path/to/file.py

```markdown 
# complete file content here
# every single line
Rules:

Output the ENTIRE file, not just changed parts
Include ALL imports, ALL functions, ALL classes
Preserve all existing code that doesn't change
Use proper language identifier in code fences
```


## templates/output_formats/diff-only.md


---
display_name: "Diff Only (unified)"
description: "Output as unified diff format"
tags: [output, diff]
---

# Output Format: Unified Diff

Output changes as unified diff format:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,6 +10,8 @@ def existing_function():
     existing_line
-    old_line
+    new_line
+    additional_line
     existing_line
Rules:

Include enough context lines (3+) for unambiguous location
Use proper --- and +++ headers with file paths
Use @@ hunk headers with line numbers
Prefix removed lines with -, added with +, context with space
```


## templates/output_formats/plan-only.md

```markdown
---
display_name: "Plan Only (no code)"
description: "Output only a structured plan, no code"
tags: [output, planning]
---

# Output Format: Plan Only

Do NOT write any code. Output ONLY a structured plan.

## Required sections:

### 1. Summary
One paragraph describing the overall approach.

### 2. Files to modify/create
List each file with a brief description of changes:
- `path/to/file.py` — what changes and why
- `path/to/new_file.py` — NEW: what this file does

### 3. Implementation steps
Numbered, ordered steps:
1. Step description (which file, what to do)
2. Next step...

### 4. Risks and considerations
- Potential issues
- Edge cases to handle
- Breaking changes if any

### 5. Testing plan
- What to test
- Key test cases
```
---
display_name: "SEARCH/REPLACE Blocks"
description: "Output as precise SEARCH/REPLACE blocks for automated application"
tags: [output, diff, automation]
---

# Output Format: SEARCH/REPLACE Blocks

For EVERY change, output it as a SEARCH/REPLACE block.

## Syntax:

## File: path/to/file.py
<<<<<<< SEARCH
exact original code to find
=======
new replacement code
>>>>>>> REPLACE

## Rules:
1. The SEARCH section must EXACTLY match existing code — same indentation, same whitespace
2. The SEARCH section must be unique within the file (include enough context)
3. Keep SEARCH blocks as small as possible while remaining unique
4. Order blocks logically: imports first, then classes, then functions
5. Each block = one logical change

## For NEW files (file doesn't exist yet):
Use empty SEARCH block:

## File: path/to/new_file.py
<<<<<<< SEARCH
=======
"""New module."""

class NewClass:
    def __init__(self):
        self.value = 42
>>>>>>> REPLACE

## For DELETING code:
Use empty REPLACE block:

## File: path/to/file.py
<<<<<<< SEARCH
def deprecated_function():
    pass
=======
>>>>>>> REPLACE

## Multiple changes in same file:
Use separate blocks for each change, in order they appear in the file.
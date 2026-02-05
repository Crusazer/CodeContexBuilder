from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class FileNode(BaseModel):
    name: str
    path: Path
    rel_path: Path
    is_dir: bool
    size: int = 0
    children: List["FileNode"] = Field(default_factory=list)

    class Config:
        frozen = False  # Разрешаем изменение children


class PromptContext(BaseModel):
    project_root: Path
    files: List[Path]
    mode_skeleton: bool = False

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def generate_sparse_file(tmp_path: Path, filename: str, size_bytes: int) -> Path:
    """Generates a sparse file with a given size and returns the file path."""
    file_path = tmp_path / filename
    with file_path.open("wb") as file_handle:
        file_handle.seek(size_bytes - 1)
        file_handle.write(b"\0")
    return file_path


def generate_file(tmp_path: Path, filename: str, file_contents: Any) -> Path:
    """Generates a test file with contents and returns the file path."""
    file_path = tmp_path / filename
    file_path.write_text(file_contents)
    return file_path


def validate_files_match(filename_a: str, filename_b: str) -> bool:
    if os.path.isfile(filename_a) is False:
        return False
    if os.path.isfile(filename_b) is False:
        return False
    with open(filename_a, "rb") as f1, open(filename_b, "rb") as f2:
        return f1.read() == f2.read()

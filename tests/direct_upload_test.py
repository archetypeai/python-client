from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from archetypeai import ArchetypeAI

from helpers import generate_file, generate_sparse_file, validate_files_match


def test_direct_upload_txt_successful(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    file_id = "direct_example.txt"
    file_contents = "Direct upload example content"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename, use_proxy=False)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_direct_upload_json_successful(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    file_id = "direct_example.json"
    file_contents = "{'foo': 'bar'}"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename, use_proxy=False)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_direct_upload_csv_successful(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    file_id = "direct_example.csv"
    file_contents = "timestamp,value_a,value_b\n1,2.2,three\n"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename, use_proxy=False)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_direct_upload_invalid_type_fails(client: ArchetypeAI, tmp_path: Path):
    filename = generate_file(tmp_path, "direct_example.foo", "Example content")

    with pytest.raises(ValueError):
        client.files.local.upload(filename, use_proxy=False)


def test_direct_upload_download_roundtrip(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    file_id = "direct_roundtrip.txt"
    file_contents = "Roundtrip test content for direct upload"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename, use_proxy=False)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True

    local_filename = tmp_path / f"downloaded_{file_id}"
    assert client.files.local.download(file_id, local_filename)

    assert validate_files_match(local_filename, filename)


def test_direct_upload_delete_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "direct_delete.txt"
    file_contents = "Content to be deleted"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename, use_proxy=False)
    assert response_data["is_valid"] is True

    response_data = client.files.local.delete(file_id)
    assert response_data["is_valid"] is True


def test_direct_upload_progress_callback(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    """Progress callback is called once per part with correct values."""
    file_id = "direct_progress.txt"
    file_contents = "Progress tracking test content"
    filename = generate_file(tmp_path, file_id, file_contents)
    file_size = os.path.getsize(filename)

    progress_calls = []
    def on_progress(completed_parts, total_parts, completed_bytes, total_bytes):
        progress_calls.append((completed_parts, total_parts, completed_bytes, total_bytes))

    response_data = client.files.local.upload(filename, use_proxy=False, on_progress=on_progress)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True

    # Small file = single part = exactly one progress call.
    assert len(progress_calls) == 1
    assert progress_calls[0] == (1, 1, file_size, file_size)


def test_direct_upload_cancel_already_set(client: ArchetypeAI, tmp_path: Path):
    """An already-set cancel event aborts before uploading parts."""
    filename = generate_file(tmp_path, "direct_cancel.txt", "Cancel test content")

    cancel = threading.Event()
    cancel.set()

    with pytest.raises(ValueError, match="Upload cancelled"):
        client.files.local.upload(filename, use_proxy=False, cancel_event=cancel)


def test_direct_upload_xl_file_multipart(client: ArchetypeAI, tmp_path: Path, uploaded_files: list[str]):
    """A 500 MB file requires 2 parts (server-side part size is 400 MB) and succeeds."""
    file_id = "direct_xl_file.txt"
    file_size_bytes = 500 * 1024**2
    filename = generate_sparse_file(tmp_path, file_id, file_size_bytes)

    progress_calls = []

    def on_progress(completed_parts, total_parts, completed_bytes, total_bytes):
        progress_calls.append((completed_parts, total_parts, completed_bytes, total_bytes))

    response_data = client.files.local.upload(filename, use_proxy=False, on_progress=on_progress)
    uploaded_files.append(file_id)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id

    assert len(progress_calls) == 2
    assert progress_calls[0][0] == 1  # first part done
    assert progress_calls[0][1] == 2  # of 2 total
    assert progress_calls[1] == (2, 2, file_size_bytes, file_size_bytes)


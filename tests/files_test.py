from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest

from archetypeai import ArchetypeAI, ApiError

from helpers import generate_file, generate_sparse_file, validate_files_match


def generate_and_upload_file(client: ArchetypeAI, tmp_path: Path, filename: str, file_contents: Any) -> Optional[Path]:
    """Generates a test file, uploads it, and returns the local path if successful."""
    filename = generate_file(tmp_path, filename, file_contents)
    response_data = client.files.local.upload(filename)
    if response_data["is_valid"] is True:
        return filename
    return None


def test_client_initialized(client: ArchetypeAI):
    assert client is not None


def test_file_upload_valid_txt_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.txt"
    file_contents = "Example content"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_file_upload_valid_text_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.text"
    file_contents = "Example content"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_file_upload_valid_json_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.json"
    file_contents = "{'foo': 'bar'}"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == "example.json"


def test_file_upload_valid_csv_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.csv"
    file_contents = "timestamp,value_a,value_b\n1,2.2,three\n"
    filename = generate_file(tmp_path, file_id, file_contents)

    response_data = client.files.local.upload(filename)
    assert response_data["is_valid"] is True
    assert response_data["file_id"] == file_id


def test_file_upload_invalid_type_fails(client: ArchetypeAI, tmp_path: Path):
    filename = generate_file(tmp_path, "example.foo", "Example content")

    with pytest.raises(ValueError):
        client.files.local.upload(filename)


def test_file_upload_xl_file_fails(client: ArchetypeAI, tmp_path: Path):
    file_size_bytes = 510 * 1024**2 # 510 MB, which is above the 500 MB limit
    filename = generate_sparse_file(tmp_path, "xl_file.txt", file_size_bytes)

    with pytest.raises(ApiError) as excinfo:
        client.files.local.upload(filename)
    api_error = excinfo.value
    assert api_error.validate_error_code_exists("request_entity_too_large") is True
    assert api_error.validate_error_count(1)


def test_file_download_txt_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.txt"
    file_contents = "Example content"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    local_filename = tmp_path / f"downloaded_{file_id}"
    assert client.files.local.download(file_id, local_filename)

    assert validate_files_match(local_filename, filename)


def test_file_download_text_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.text"
    file_contents = "Example content"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    local_filename = tmp_path / f"downloaded_{file_id}"
    assert client.files.local.download(file_id, local_filename)

    assert validate_files_match(local_filename, filename)


def test_file_download_json_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.json"
    file_contents = "{'foo': 'bar'}"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    local_filename = tmp_path / f"downloaded_{file_id}"
    assert client.files.local.download(file_id, local_filename)

    assert validate_files_match(local_filename, filename)


def test_file_download_csv_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.csv"
    file_contents = "timestamp,value_a,value_b\n1,2.2,three\n"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    local_filename = tmp_path / f"downloaded_{file_id}"
    assert client.files.local.download(file_id, local_filename)

    assert validate_files_match(local_filename, filename)


def test_file_delete_txt_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.txt"
    file_contents = "Example content"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    response_data = client.files.local.delete(file_id)
    assert response_data["is_valid"] is True


def test_file_delete_text_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.text"
    file_contents = "Example content"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    response_data = client.files.local.delete(file_id)
    assert response_data["is_valid"] is True


def test_file_delete_json_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.json"
    file_contents = "{'foo': 'bar'}"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    response_data = client.files.local.delete(file_id)
    assert response_data["is_valid"] is True

def test_file_delete_csv_successful(client: ArchetypeAI, tmp_path: Path):
    file_id = "example.csv"
    file_contents = "timestamp,value_a,value_b\n1,2.2,three\n"
    filename = generate_and_upload_file(client, tmp_path, file_id, file_contents)
    assert filename is not None

    response_data = client.files.local.delete(file_id)
    assert response_data["is_valid"] is True

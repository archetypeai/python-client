from typing import Any, Optional
import logging
import os
from pathlib import Path
import pytest

from archetypeai import ArchetypeAI, ApiError


@pytest.fixture
def client() -> ArchetypeAI:
    """Attempts to initialize a client, if it fails it skips the tests."""
    api_key = os.getenv("ATAI_API_KEY", None)
    api_endpoint = os.getenv("ATAI_API_ENDPOINT", None)

    if api_key is None or api_endpoint is None:
        pytest.skip("Client is not initialized!")

    client = ArchetypeAI(api_key, api_endpoint=api_endpoint, request_timeout_sec=30)

    return client


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


def generate_and_upload_file(client: ArchetypeAI, tmp_path: Path, filename: str, file_contents: Any) -> Optional[Path]:
    """Generates a test file, uploads it, and returns the local path if successful."""
    filename = generate_file(tmp_path, filename, file_contents)
    response_data = client.files.local.upload(filename)
    if response_data["is_valid"] is True:
        return filename
    return None


def validate_files_match(filename_a: str, filename_b: str) -> bool:
    if os.path.isfile(filename_a) is False: 
        return False
    if os.path.isfile(filename_b) is False: 
        return False
    with open(filename_a, "rb") as f1, open(filename_b, "rb") as f2:
        return f1.read() == f2.read()


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
    file_size_bytes = 500 * 1024**2
    filename = generate_sparse_file(tmp_path, "xl_file.txt", file_size_bytes)

    with pytest.raises(ApiError) as excinfo:
        client.files.local.upload(filename)
    api_error = excinfo.value
    assert api_error.validate_error_code_exists("invalid_file_size") is True
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
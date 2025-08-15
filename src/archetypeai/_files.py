from typing import Dict, Union

import logging
import os
import json

from requests_toolbelt import MultipartEncoder

from archetypeai._base import ApiBase


class FilesApiBase(ApiBase):
    """Common file ops shared across all file APIs."""

    def get_info(self) -> dict:
        """Gets the file info for all the files your org has uploaded to the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "files/info")
        return self.requests_get(api_endpoint)

    def get_metadata(self, shard_index: int = -1, max_items_per_shard: int = -1, file_id: Union[str, None] = None) -> dict:
        """Gets a list of metadata about any files your org has uploaded to the Archetype AI platform.

        Use the shard_index and max_items_per_shard to retrieve metadata about a subset of files.

        Use the file_id argument to retrieve the metadata for a specific file.
        """
        if file_id is None:
            api_endpoint = self._get_endpoint(self.api_endpoint, "files/metadata")
            params = {"shard_index": shard_index, "max_items_per_shard": max_items_per_shard}
        else:
            api_endpoint = self._get_endpoint(self.api_endpoint, f"files/metadata/{file_id}")
            params = {}
        return self.requests_get(api_endpoint, params=params)


class LocalFilesApi(FilesApiBase):
    """API for working with local files."""

    def upload(self, filename: str, base64_data: Union[str, None] = None) -> dict:
        """Uploads a local file to the Archetype AI platform."""
        if base64_data is None:
            response = self._upload_file(filename)
        else:
            response = self._upload_base64_data(filename, base64_data)
        assert "file_id" in response, response
        return response
        
    def _upload_file(self, filename: str) -> dict:
        api_endpoint = self._get_endpoint(self.api_endpoint, "files")
        with open(filename, "rb") as file_handle:
            encoder = MultipartEncoder(
                {"file": (os.path.basename(filename), file_handle.read(), self.get_file_type(filename))})
            response_data = self.requests_post(
                api_endpoint, data_payload=encoder, additional_headers={"Content-Type": encoder.content_type}
            )
            return response_data
    
    def _upload_base64_data(self, filename: str, base64_data: str) -> dict:
        api_endpoint = self._get_endpoint(self.api_endpoint, "files/base64")
        encoder = MultipartEncoder(
            {"file": (os.path.basename(filename), base64_data, self.get_file_type(filename))})
        response_data = self.requests_post(
            api_endpoint, data_payload=encoder, additional_headers={"Content-Type": encoder.content_type}
        )
        return response_data

    def delete(self, filename: str) -> dict:
        """Deletes a file that was previously uploaded to the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"files/delete/{filename}")
        return self.requests_delete(api_endpoint)

    def download(self, filename: str, local_filename: str = "") -> bool:
        """Downloads a file that was previously uploaded to the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"files/download/{filename}")
        # If the local filename is not set then download the file using the remote filename.
        if local_filename == "":
            local_filename = filename
        response = self.requests_download(api_endpoint)
        success = response.status_code == 200
        if success:
            with open(local_filename, "wb") as file_handle:
                    file_handle.write(response.content)
        return success


class S3FilesApi(FilesApiBase):
    """API for working with Amazon s3 files."""

    def upload(self, filenames: list[str], credentials: Union[Dict[str, str], None] = None, batch_size: int = 64) -> dict:
        """Uploads a list of s3 files directly to the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "files/s3")
        num_files = len(filenames)
        response_data = []
        for batch_start in range(0, num_files, batch_size):
            batch_end = min(batch_start + batch_size, num_files)
            data_payload = {"credentials": credentials, "filenames": filenames[batch_start:batch_end]}
            response_data.append(self.requests_post(api_endpoint, data_payload=json.dumps(data_payload)))
        return response_data


class FilesApi(FilesApiBase):
    """Main class for handling all file API calls."""

    local: LocalFilesApi
    s3: S3FilesApi

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.local = LocalFilesApi(api_key, api_endpoint)
        self.s3 = S3FilesApi(api_key, api_endpoint)
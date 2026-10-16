from typing import Iterator, Union

import logging
import os

from requests_toolbelt import MultipartEncoder

from archetypeai._base import ApiBase


class FilesApiBase(ApiBase):
    """Common file ops shared across all file APIs."""

    def get_info(self) -> dict:
        """Gets the file info for all the files your org has uploaded to the Archetype AI platform."""
        api_endpoint = self._get_endpoint(self.api_endpoint, "files/info")
        return self.requests_get(api_endpoint)

    def get_metadata(
        self,
        limit: Union[int, None] = None,
        after: Union[str, None] = None,
        before: Union[str, None] = None,
        file_id: Union[str, None] = None,
    ) -> dict:
        """Gets one page of metadata about the files your org has uploaded to the Archetype AI platform.

        The page is `{"data": [...], "has_more": bool, "next_cursor": str | None, "prev_cursor": str | None}`,
        newest first, with up to `limit` files (default 100, at most 1000). Pass a page's `next_cursor` as
        `after` to fetch the following page, or its `prev_cursor` as `before` to step back; the two are
        mutually exclusive. Use `iter_metadata` to walk every file.

        Use the file_id argument to retrieve the metadata for a specific file instead.
        """
        if file_id is None:
            api_endpoint = self._get_endpoint(self.api_endpoint, "files/metadata")
            params = {k: v for k, v in {"limit": limit, "after": after, "before": before}.items() if v is not None}
        else:
            api_endpoint = self._get_endpoint(self.api_endpoint, f"files/metadata/{file_id}")
            params = {}
        return self.requests_get(api_endpoint, params=params)

    def iter_metadata(self, limit: int = 100) -> Iterator[dict]:
        """Yields the metadata of every file your org has uploaded, newest first, fetching `limit` files per request."""
        after: Union[str, None] = None
        while True:
            page = self.get_metadata(limit=limit, after=after)
            yield from page["data"]
            after = page.get("next_cursor")
            if not page.get("has_more") or after is None:
                return


class LocalFilesApi(FilesApiBase):
    """API for working with local files."""

    def upload(self, filename: str, base64_data: Union[str, None] = None, use_proxy: bool = True,
               max_workers: int = 8, on_progress=None, cancel_event=None,
               allow_resume: bool = False, disable_checkpointing: bool = False) -> dict:
        """Uploads a local file to the Archetype AI platform.

        Args:
            filename: Path to the local file to upload.
            base64_data: Optional base64-encoded file data. If provided, uploads via proxy.
            use_proxy: If True (default), uploads through the platform proxy.
                       If False, uploads directly to cloud storage using presigned URLs.
            max_workers: Maximum number of concurrent part upload threads (only used with use_proxy=False).
            on_progress: Optional callback called after each part completes (only used with use_proxy=False).
                         Signature: on_progress(completed_parts, total_parts, completed_bytes, total_bytes).
                         If ``allow_resume`` is True and the server resumes an existing upload,
                         the callback is also invoked once right away with the counts of parts
                         and bytes already uploaded in a previous session.
            cancel_event: Optional threading.Event that can be set to cancel the upload
                          (only used with use_proxy=False).
            allow_resume: If True, a matching in-progress upload (same filename, file_type
                          and size) is reused on the server, and parts already checkpointed
                          are skipped. Defaults to False. Only used with use_proxy=False.
            disable_checkpointing: If True, parts are not checkpointed after each successful
                                   upload. Defaults to False. Only used with use_proxy=False.
        """
        if base64_data is not None:
            if not use_proxy:
                logging.warning("Base64 upload is currently only supported by proxy uploads but `use_proxy=False` was provided; defaulting to using the proxy")
            response = self._upload_base64_data(filename, base64_data)
        elif use_proxy:
            response = self._upload_file(filename)
        else:
            response = self._upload_file_direct(
                filename, max_workers, on_progress, cancel_event,
                allow_resume=allow_resume, disable_checkpointing=disable_checkpointing,
            )
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

    def _upload_file_direct(self, filename: str, max_workers: int = 8,
                            on_progress=None, cancel_event=None,
                            allow_resume: bool = False, disable_checkpointing: bool = False) -> dict:
        from archetypeai._direct_upload import direct_upload
        return direct_upload(
            api=self,
            filepath=filename,
            file_type=self.get_file_type(filename),
            max_workers=max_workers,
            on_progress=on_progress,
            cancel_event=cancel_event,
            allow_resume=allow_resume,
            disable_checkpointing=disable_checkpointing,
        )

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


class FilesApi(FilesApiBase):
    """Main class for handling all file API calls."""

    local: LocalFilesApi

    def __init__(self, api_key: str, api_endpoint: str) -> None:
        super().__init__(api_key, api_endpoint)
        self.local = LocalFilesApi(api_key, api_endpoint)

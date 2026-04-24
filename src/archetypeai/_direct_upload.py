"""Implements the direct-to-cloud file upload path using presigned URLs."""

import json
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


# Status codes that are worth retrying on presigned URL PUTs.
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

_INITIAL_BACKOFF_SEC = 0.5
_MAX_BACKOFF_SEC = 30.0

# Used as `requests.put(url, data=reader)`. Under the hood, urllib3 calls
# `reader.read(blocksize)` in a loop (blocksize defaults to 16 KiB — see
# https://github.com/urllib3/urllib3/issues/3066), so at most one 16 KiB chunk
# is buffered in memory at a time regardless of part size. `__len__` is used by
# requests (via `super_len()`) to set the ``Content-Length`` header.
class FilePartReader:
    """A file-like object that reads a specific byte range from a file.

    Each instance opens its own file handle so multiple threads can read
    different parts of the same file concurrently without locking.
    """

    def __init__(self, filepath, offset, length):
        self._filepath = filepath
        self._offset = offset
        self.length = length
        self._file = open(filepath, "rb")
        self._file.seek(offset)
        self._bytes_remaining = length

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def read(self, size=-1):
        if self._bytes_remaining <= 0:
            return b""
        if size == -1:
            size = self._bytes_remaining
        to_read = min(size, self._bytes_remaining)
        data = self._file.read(to_read)
        self._bytes_remaining -= len(data)
        return data

    def __len__(self):
        return self.length

    def reset(self):
        """Re-seek to the start of the part for retry."""
        self._file.seek(self._offset)
        self._bytes_remaining = self.length

    def close(self):
        self._file.close()


def _is_expired_url_error(status_code, body):
    """Whether a PUT failure indicates that the presigned URL has expired.

    S3 returns 403 when the signature itself has expired, and can return 400 with
    a ``TokenExpired`` error code when the underlying STS credentials used to sign
    the URL have expired. The 400 check is deliberately conservative — we just look
    for the specific code substring rather than parsing the XML body, so for non-S3
    URLs this is effectively a no-op.
    """
    return status_code == 403 or (status_code == 400 and "TokenExpired" in body)


def _generate_upload_urls(api, upload_id, part_numbers):
    """Calls the regenerate upload URLs endpoint for the given part numbers."""
    payload = {"part_numbers": part_numbers}
    endpoint = api._get_endpoint(api.api_endpoint, "files/uploads", upload_id, "parts/urls")
    return api.requests_post(
        endpoint,
        data_payload=json.dumps(payload),
        additional_headers={"Content-Type": "application/json"},
    )


def _refresh_part_url(api, upload_id, part_number):
    """Returns a fresh presigned URL for a single part."""
    response = _generate_upload_urls(api, upload_id, [part_number])
    for part in response.get("parts", []):
        if part.get("part_number") == part_number:
            return part["url"]
    raise ValueError(f"generate_upload_urls returned no URL for part {part_number}")


def _upload_part_with_retry(api, upload_id, part_info, filepath, max_retries=3, cancel_event=None, timeout_sec=None):
    """Uploads a single part to a presigned URL with exponential backoff.

    If the PUT fails with an "expired URL" error (403, or 400 with TokenExpired), the
    URL is refreshed via the regenerate-URLs endpoint and the PUT is retried. The first
    refresh is free: no backoff and it does not count against ``max_retries``. Subsequent
    expired-URL errors count as regular retries, with backoff.

    Args:
        api: An ApiBase instance (used to call the regenerate-URLs endpoint).
        upload_id: The in-progress upload's ID (used to refresh URLs).
        part_info: Dict with keys: part_number, url, offset, length.
        filepath: Path to the source file on disk.
        max_retries: Maximum number of retry attempts.
        cancel_event: Optional threading.Event; if set, the upload is cancelled.
        timeout_sec: Optional timeout in seconds for each PUT request.

    Returns:
        Dict with part_number and part_token (etag from response).

    Raises:
        ValueError: If the upload fails after all retries or is cancelled.
        requests.HTTPError: On non-retryable HTTP errors.
    """
    with FilePartReader(filepath, part_info["offset"], part_info["length"]) as reader:
        last_error = None
        part_number = part_info['part_number']
        url = part_info["url"]
        has_refreshed = False
        attempt = 0
        while attempt < max_retries:
            if cancel_event is not None and cancel_event.is_set():
                raise ValueError("Upload cancelled")

            # If it is a retry, apply backoff before retrying.
            if attempt > 0:
                reader.reset()
                backoff = min(_INITIAL_BACKOFF_SEC * (2 ** attempt), _MAX_BACKOFF_SEC)
                jitter = random.uniform(0, backoff * 0.25)
                if cancel_event is not None:
                    if cancel_event.wait(backoff + jitter):
                        raise ValueError("Upload cancelled")
                else:
                    time.sleep(backoff + jitter)

            try:
                response = requests.put(
                    url,
                    data=reader,
                    headers={"Content-Length": str(reader.length)},
                    timeout=timeout_sec,
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                logging.warning(f"Part {part_number}: network error on attempt {attempt + 1}: {exc}")
                last_error = exc
                attempt += 1
                continue

            if response.status_code in (200, 201):
                etag = response.headers.get("etag", "")
                return {"part_number": part_number, "part_token": etag}

            if _is_expired_url_error(response.status_code, response.text):
                if not has_refreshed:
                    has_refreshed = True
                    logging.debug(
                        f"Part {part_number}: presigned URL expired (status {response.status_code}), refreshing"
                    )
                    url = _refresh_part_url(api, upload_id, part_number)
                    reader.reset()
                    continue
                logging.warning(
                    f"Part {part_number}: presigned URL expired again after refresh on attempt "
                    f"{attempt + 1}, retrying with a new URL..."
                )
                url = _refresh_part_url(api, upload_id, part_number)
                last_error = ValueError(f"HTTP {response.status_code}: {response.text}")
                attempt += 1
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES:
                logging.warning(
                    f"Part {part_number}: got {response.status_code} on attempt {attempt + 1}, retrying..."
                )
                last_error = ValueError(f"HTTP {response.status_code}: {response.text}")
                attempt += 1
                continue

            # Non-retryable error.
            response.raise_for_status()

        raise ValueError(
            f"Part {part_number} failed after {max_retries} attempts: {last_error}"
        )


def _initiate_upload(api, filepath, file_type, resume_if_started=False):
    """Calls the initiate upload endpoint.

    When ``resume_if_started`` is True, if a matching in-progress upload already exists
    for this (org, filename), the server reuses it and returns only the parts not yet
    checkpointed (with ``is_resume=True`` in the response).

    Returns the parsed response dict with upload_id, parts, etc.
    """
    filename = os.path.basename(filepath)
    num_bytes = os.path.getsize(filepath)
    payload = {
        "filename": filename,
        "file_type": file_type,
        "num_bytes": num_bytes,
    }
    if resume_if_started:
        payload["resume_if_started"] = True
    endpoint = api._get_endpoint(api.api_endpoint, "files/uploads/initiate")
    return api.requests_post(
        endpoint,
        data_payload=json.dumps(payload),
        additional_headers={"Content-Type": "application/json"},
    )


def _complete_upload(api, upload_id, completed_parts):
    """Calls the complete upload endpoint.

    Returns the parsed response dict with file_uid, file_name, etc.
    """
    payload = {"parts": completed_parts}
    endpoint = api._get_endpoint(api.api_endpoint, "files/uploads", upload_id, "complete")
    return api.requests_post(
        endpoint,
        data_payload=json.dumps(payload),
        additional_headers={"Content-Type": "application/json"},
    )


def _abort_upload(api, upload_id):
    """Best-effort abort of an in-progress upload."""
    try:
        endpoint = api._get_endpoint(api.api_endpoint, "files/uploads", upload_id, "abort")
        api.requests_post(
            endpoint,
            data_payload=json.dumps({}),
            additional_headers={"Content-Type": "application/json"},
        )
    except Exception as exc:
        logging.warning(f"Failed to abort upload {upload_id}: {exc}")


def _checkpoint_parts(api, upload_id, parts):
    """Best-effort checkpoint of a subset of an upload's parts.

    The server stores each part's token so that a subsequent initiate with
    ``resume_if_started=True`` returns only the not-yet-checkpointed parts.
    Failures are logged but not propagated — callers treat checkpointing as
    non-essential.
    """
    try:
        payload = {"parts": parts}
        endpoint = api._get_endpoint(api.api_endpoint, "files/uploads", upload_id, "parts/checkpoint")
        api.requests_post(
            endpoint,
            data_payload=json.dumps(payload),
            additional_headers={"Content-Type": "application/json"},
        )
    except Exception as exc:
        logging.warning(f"Checkpoint for upload {upload_id} failed: {exc}")


def direct_upload(api, filepath, file_type, max_workers=8, on_progress=None, cancel_event=None,
                  allow_resume=False, disable_checkpointing=False):
    """Performs a direct-to-cloud upload using presigned URLs.

    Args:
        api: An ApiBase instance (provides auth, retry, endpoint building).
        filepath: Path to the local file on disk.
        file_type: MIME type string for the file.
        max_workers: Maximum number of concurrent part upload threads.
        on_progress: Optional callback called after each part completes.
                     Signature: on_progress(completed_parts, total_parts, completed_bytes, total_bytes).
                     If ``allow_resume`` is True and the server resumes an existing
                     upload, the callback is also invoked once immediately with the
                     counts of parts/bytes already uploaded in a previous session.
        cancel_event: Optional threading.Event; if set, the upload is cancelled.
        allow_resume: When True, the initiate request asks the server to reuse an
                      existing in-progress upload for the same filename (same file_type
                      and num_bytes) if one exists. Parts that have already been
                      checkpointed server-side are skipped. Defaults to False.
        disable_checkpointing: When True, the client will not checkpoint each part
                               as it is uploaded. Defaults to False — the common
                               case is to checkpoint so that a later call with
                               ``allow_resume=True`` can skip already-uploaded parts.

    Returns:
        Dict matching the proxy upload format: {"is_valid": True, "file_id": ..., "file_uid": ...}
    """
    if cancel_event is None:
        cancel_event = threading.Event()

    upload_id = None
    checkpoint_executor = None
    try:
        initiate_response = _initiate_upload(api, filepath, file_type, resume_if_started=allow_resume)
        upload_id = initiate_response["upload_id"]
        parts = initiate_response["parts"]
        if cancel_event.is_set():
            raise ValueError("Upload cancelled")

        # When the server resumed a prior upload, ``parts`` only contains the parts
        # that still need to be uploaded. Use the response-level totals so we report
        # progress against the full file.
        total_bytes = initiate_response.get("total_bytes")
        if total_bytes is None:
            total_bytes = sum(p["length"] for p in parts)
        total_parts = initiate_response.get("num_parts")
        if total_parts is None:
            total_parts = len(parts)

        is_resume = initiate_response.get("is_resume", False)
        remaining_bytes = sum(p["length"] for p in parts)
        completed_bytes = total_bytes - remaining_bytes if is_resume else 0
        completed_count = total_parts - len(parts) if is_resume else 0

        if is_resume and on_progress is not None and completed_count > 0:
            on_progress(completed_count, total_parts, completed_bytes, total_bytes)

        completed_parts = []

        if not disable_checkpointing:
            # Separate executor so checkpoint requests do not share slots with part
            # uploads. Each submission is fire-and-forget; we never block on results.
            checkpoint_executor = ThreadPoolExecutor(max_workers=4)

        if parts:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(parts))) as executor:
                futures = {
                    executor.submit(
                        _upload_part_with_retry, api, upload_id, part, filepath, api.num_retries,
                        cancel_event, api.request_timeout_sec,
                    ): part
                    for part in parts
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                    except Exception:
                        cancel_event.set()
                        raise
                    completed_parts.append(result)
                    completed_count += 1
                    completed_bytes += futures[future]["length"]
                    if on_progress is not None:
                        on_progress(completed_count, total_parts, completed_bytes, total_bytes)
                    if checkpoint_executor is not None:
                        checkpoint_executor.submit(_checkpoint_parts, api, upload_id, [result])

        completed_parts.sort(key=lambda p: p["part_number"])
        complete_response = _complete_upload(api, upload_id, completed_parts)
        return {"is_valid": True, "file_id": complete_response["file_name"], "file_uid": complete_response["file_uid"]}

    except Exception:
        if upload_id is not None:
            _abort_upload(api, upload_id)
        raise
    finally:
        if checkpoint_executor is not None:
            # Don't block on pending checkpoints: they are best-effort and the
            # upload is already complete (or aborted). ThreadPoolExecutor worker
            # threads are daemons, so in-flight checkpoints keep running but won't
            # prevent the interpreter from exiting.
            checkpoint_executor.shutdown(wait=False)

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx


_BUCKET = "rebuild-agent"
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CONTENT_RANGE_PATTERN = re.compile(r"^(?:([0-9]+)-([0-9]+)|[*])/([0-9]+|[*])$")
_PAGE_SIZE = 1000
_MAX_PAGES = 10_000


class StorageError(RuntimeError):
    """A sanitized Supabase database or object storage failure."""


class PermissionDeniedError(StorageError):
    pass


class NotFoundError(StorageError):
    pass


class ConflictError(StorageError):
    code = "VERSION_CONFLICT"


class StorageUnavailableError(StorageError):
    pass


class SupabaseStore:
    def __init__(
        self,
        url: str,
        publishable_key: str,
        access_token: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not url or not publishable_key or not access_token:
            raise ValueError("Supabase URL, publishable key, and access token are required")
        self._url = url.rstrip("/")
        self._publishable_key = publishable_key
        self._access_token = access_token
        self._client = client or httpx.Client()
        self._timeout = timeout
        self._owner_id: str | None = None

    def close(self) -> None:
        self._client.close()

    def list(self, kind: str, project_id: str | None = None) -> list[dict[str, Any]]:
        self._validate_kind(kind)
        params = {
            "select": "id,kind,project_id,payload,version,created_at,updated_at",
            "kind": f"eq.{kind}",
            "order": "updated_at.desc,id.asc",
        }
        if project_id is not None:
            self._validate_identifier(project_id, "project id")
            params["project_id"] = f"eq.{project_id}"

        entities: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        offset = 0
        for _ in range(_MAX_PAGES):
            response = self._request(
                "GET",
                "/rest/v1/rb_entities",
                params=params,
                headers={
                    "Range-Unit": "items",
                    "Range": f"{offset}-{offset + _PAGE_SIZE - 1}",
                },
            )
            rows = self._rows(response)
            if not rows:
                return entities

            page_entities = [self._entity(row) for row in rows]
            page_ids = [entity["id"] for entity in page_entities]
            if (
                any(not isinstance(entity_id, str) or not entity_id for entity_id in page_ids)
                or len(page_ids) != len(set(page_ids))
                or bool(seen_ids.intersection(page_ids))
            ):
                raise StorageUnavailableError("Supabase pagination incomplete")
            seen_ids.update(page_ids)
            entities.extend(page_entities)

            next_offset, complete = self._pagination_progress(
                response,
                expected_start=offset,
                row_count=len(rows),
            )
            if complete:
                return entities
            if next_offset <= offset:
                raise StorageUnavailableError("Supabase pagination incomplete")
            offset = next_offset

        raise StorageUnavailableError("Supabase pagination incomplete")

    def approve(
        self,
        draft_id: str,
        expected_version: int,
        draft_payload: Mapping[str, Any],
        approval_id: str,
        approval_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_identifier(draft_id, "draft id")
        self._validate_identifier(approval_id, "approval id")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("expected version must be a positive integer")
        if not isinstance(draft_payload, Mapping) or not isinstance(approval_payload, Mapping):
            raise ValueError("approval payloads must be objects")
        response = self._request(
            "POST",
            "/rest/v1/rpc/rb_approve_draft",
            json={
                "draft_id": draft_id,
                "expected_version": expected_version,
                "draft_payload": dict(draft_payload),
                "approval_id": approval_id,
                "approval_payload": dict(approval_payload),
            },
            conflict_message="approval version conflict",
        )
        rows = self._rows(response)
        if len(rows) != 1:
            raise ConflictError("approval transaction did not return a draft")
        return self._entity(rows[0])

    def get(self, id: str) -> dict[str, Any] | None:
        self._validate_identifier(id, "entity id")
        response = self._request(
            "GET",
            "/rest/v1/rb_entities",
            params={
                "select": "id,kind,project_id,payload,version,created_at,updated_at",
                "id": f"eq.{id}",
                "limit": "1",
            },
        )
        rows = self._rows(response)
        return self._entity(rows[0]) if rows else None

    def save(
        self,
        kind: str,
        id: str,
        project_id: str | None,
        payload: Mapping[str, Any],
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        self._validate_kind(kind)
        self._validate_identifier(id, "entity id")
        if project_id is not None:
            self._validate_identifier(project_id, "project id")
        if not isinstance(payload, Mapping):
            raise ValueError("entity payload must be an object")

        body: dict[str, Any] = {
            "kind": kind,
            "project_id": project_id,
            "payload": dict(payload),
        }
        headers = {"Prefer": "return=representation"}
        if expected_version is None:
            body["id"] = id
            response = self._request(
                "POST",
                "/rest/v1/rb_entities",
                json=body,
                headers=headers,
                conflict_message="entity already exists",
            )
        else:
            if type(expected_version) is not int or expected_version < 1:
                raise ValueError("expected version must be a positive integer")
            body["version"] = expected_version + 1
            response = self._request(
                "PATCH",
                "/rest/v1/rb_entities",
                params={"id": f"eq.{id}", "version": f"eq.{expected_version}"},
                json=body,
                headers=headers,
            )

        rows = self._rows(response)
        if not rows:
            raise ConflictError("stale entity version")
        return self._entity(rows[0])

    def upload_bytes(self, path: str, data: bytes, content_type: str) -> dict[str, Any]:
        safe_path = self._validate_storage_path(path)
        if not isinstance(data, bytes):
            raise ValueError("storage data must be bytes")
        if not content_type:
            raise ValueError("content type is required")
        object_path = self._owned_object_path(safe_path)
        self._request(
            "POST",
            f"/storage/v1/object/{_BUCKET}/{object_path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "false"},
            conflict_message="storage object already exists",
        )
        return {"path": safe_path, "size": len(data), "content_type": content_type}

    def download_bytes(self, path: str) -> bytes:
        safe_path = self._validate_storage_path(path)
        object_path = self._owned_object_path(safe_path)
        response = self._request(
            "GET",
            f"/storage/v1/object/{_BUCKET}/{object_path}",
            not_found_message="storage object not found",
        )
        return response.content

    def _owned_object_path(self, path: str) -> str:
        if self._owner_id is None:
            response = self._request("GET", "/auth/v1/user")
            try:
                data = response.json()
            except ValueError as exc:
                raise StorageUnavailableError("authentication service returned an invalid response") from exc
            owner_id = data.get("id") if isinstance(data, Mapping) else None
            if not isinstance(owner_id, str) or not owner_id:
                raise StorageUnavailableError("authentication service returned an invalid response")
            self._owner_id = owner_id
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        return f"{quote(self._owner_id, safe='')}/{encoded}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        conflict_message: str = "write conflict",
        not_found_message: str = "resource not found",
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        request_headers = {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {self._access_token}",
        }
        if headers:
            request_headers.update(headers)
        try:
            response = self._client.request(
                method,
                f"{self._url}{path}",
                headers=request_headers,
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise StorageUnavailableError("Supabase service unavailable") from exc
        if response.status_code in (401, 403):
            raise PermissionDeniedError("Supabase access denied")
        # Supabase Storage may transport NoSuchKey as HTTP 400 with an enclosed
        # 404. Treat only an object GET with this exact code as absent bytes;
        # authorization, bucket and mutation errors must remain failures.
        missing_object = (
            response.status_code == 400
            and method == "GET"
            and path.startswith(f"/storage/v1/object/{_BUCKET}/")
            and self._error_code(response) == "NoSuchKey"
        )
        if response.status_code == 404 or missing_object:
            raise NotFoundError(not_found_message)
        if response.status_code in (409, 412) or self._error_code(response) == "40001":
            raise ConflictError(conflict_message)
        if response.status_code >= 500:
            raise StorageUnavailableError("Supabase service unavailable")
        if response.status_code >= 400:
            raise StorageError("Supabase request failed")
        return response

    @staticmethod
    def _error_code(response: httpx.Response) -> str | None:
        if response.status_code < 400:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        code = data.get("code") if isinstance(data, Mapping) else None
        return code if isinstance(code, str) else None

    @staticmethod
    def _pagination_progress(
        response: httpx.Response,
        *,
        expected_start: int,
        row_count: int,
    ) -> tuple[int, bool]:
        content_range = response.headers.get("Content-Range")
        if content_range is None:
            return expected_start + row_count, False
        match = _CONTENT_RANGE_PATTERN.fullmatch(content_range)
        if match is None or match.group(1) is None or match.group(2) is None:
            raise StorageUnavailableError("Supabase pagination incomplete")

        actual_start = int(match.group(1))
        actual_end = int(match.group(2))
        if (
            actual_start != expected_start
            or actual_end < actual_start
            or actual_end - actual_start + 1 != row_count
        ):
            raise StorageUnavailableError("Supabase pagination incomplete")

        next_offset = actual_end + 1
        total_text = match.group(3)
        if total_text == "*":
            return next_offset, False
        total = int(total_text)
        if total < next_offset:
            raise StorageUnavailableError("Supabase pagination incomplete")
        return next_offset, next_offset == total

    @staticmethod
    def _rows(response: httpx.Response) -> list[Mapping[str, Any]]:
        try:
            data = response.json()
        except ValueError as exc:
            raise StorageUnavailableError("Supabase returned an invalid response") from exc
        if not isinstance(data, list) or any(not isinstance(row, Mapping) for row in data):
            raise StorageUnavailableError("Supabase returned an invalid response")
        return data

    @staticmethod
    def _entity(row: Mapping[str, Any]) -> dict[str, Any]:
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            raise StorageUnavailableError("Supabase returned an invalid entity")
        return {
            "id": row.get("id"),
            "kind": row.get("kind"),
            "project_id": row.get("project_id"),
            "payload": dict(payload),
            "version": row.get("version"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _validate_kind(kind: str) -> None:
        if not isinstance(kind, str) or not _KIND_PATTERN.fullmatch(kind):
            raise ValueError("invalid entity kind")

    @staticmethod
    def _validate_identifier(value: str, label: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(f"invalid {label}")

    @staticmethod
    def _validate_storage_path(path: str) -> str:
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise ValueError("invalid storage path")
        pure_path = PurePosixPath(path)
        if any(part in ("", ".", "..") for part in pure_path.parts):
            raise ValueError("invalid storage path")
        normalized = str(pure_path)
        if normalized != path or chr(92) in path:
            raise ValueError("invalid storage path")
        return normalized

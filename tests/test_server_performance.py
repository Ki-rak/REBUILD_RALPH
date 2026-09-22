from collections import Counter
from copy import deepcopy
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.server import Context, create_app
from backend.storage import ConflictError, NotFoundError


class CountingStorage:
    def __init__(self, owner, records, files, calls):
        self.owner = owner
        self.records = records
        self.files = files
        self.calls = calls

    def list(self, kind, project_id=None):
        self.calls[("list", kind, project_id)] += 1
        return deepcopy([
            value for (owner, _), value in self.records.items()
            if owner == self.owner and value["kind"] == kind
            and (project_id is None or value["project_id"] == project_id)
        ])

    def get(self, entity_id):
        self.calls[("get", entity_id)] += 1
        return deepcopy(self.records.get((self.owner, entity_id)))

    def save(self, kind, entity_id, project_id, payload, expected_version=None):
        self.calls[("save", kind)] += 1
        previous = self.records.get((self.owner, entity_id))
        if expected_version is not None and (not previous or previous["version"] != expected_version):
            raise RuntimeError("test conflict")
        entity = {
            "id": entity_id,
            "kind": kind,
            "project_id": project_id,
            "payload": deepcopy(payload),
            "version": previous["version"] + 1 if previous else 1,
        }
        self.records[(self.owner, entity_id)] = entity
        return deepcopy(entity)

    def upload_bytes(self, path, data, content_type):
        self.calls[("upload", content_type)] += 1
        if path in self.files:
            raise ConflictError("immutable object already exists")
        self.files[path] = bytes(data)
        return {"path": path}

    def download_bytes(self, path):
        self.calls[("download", path)] += 1
        if path not in self.files:
            raise NotFoundError("missing")
        return self.files[path]


class FakeAuth:
    def logout(self, token):
        return None


def test_two_file_upload_reuses_request_local_project_and_lists():
    owner = str(uuid4())
    records, files, calls = {}, {}, Counter()

    def context(token):
        if token != "alice":
            raise HTTPException(401)
        return Context(
            {"id": owner, "email": "alice@example.invalid"},
            CountingStorage(owner, records, files, calls),
            FakeAuth(),
            token,
        )

    app = create_app(
        Settings(
            "https://wsziosnttnxefgfbgpeq.supabase.co",
            "test-publishable",
            "local",
            approval_signing_key="isolated-test-integrity-key-not-production",
        ),
        context_factory=context,
    )
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer alice"}
    created = client.post("/api/projects", json={"name": "Perf", "kind": "current"}, headers=headers)
    assert created.status_code == 201
    project_id = created.json()["id"]
    calls.clear()

    response = client.post(
        f"/api/projects/{project_id}/upload",
        files=[
            ("files", ("one.txt", b"Notice: 10 calendar days.", "text/plain")),
            ("files", ("two.txt", b"Notice: 12 calendar days.", "text/plain")),
        ],
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()["documents"]) == 2
    assert calls[("get", project_id)] == 1
    assert calls[("list", "document", project_id)] == 1
    assert calls[("list", "draft", project_id)] == 1
    assert calls[("list", "project", None)] == 0
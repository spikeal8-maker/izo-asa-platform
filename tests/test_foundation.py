import base64
import gzip
import itertools
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from izo.app import create_app
from izo.config import Settings
from izo.contracts import Capability, Executor, JobSpec, JobState, Modality
from izo.generation import ALLOWED, pool_for, resolve_capability, transition
from izo.health import dependencies_ready
from izo.storage import S3Store, validate_key
from tools.bootstrap import bootstrap


@pytest.mark.parametrize("ready", [True, False])
def test_liveness_is_not_readiness(ready):
    with TestClient(create_app(Settings(), readiness=lambda: ready)) as client:
        assert client.get("/api/health/live").json() == {"ok": True}
        r = client.get("/api/health/ready")
        assert r.status_code == (200 if ready else 503)
        assert r.json() == {"ready": ready}
        assert len(r.headers["X-Request-ID"]) == 32
        assert r.headers["cache-control"] == "no-store"


def test_no_fake_generators_or_identity():
    with TestClient(create_app(Settings(), readiness=lambda: True)) as client:
        r = client.get("/api/v1/foundation")
        assert {v["modality"] for v in r.json()["capabilities"]} == {m.value for m in Modality}
        assert all(not v["available"] for v in r.json()["capabilities"])
        for path in ["/api/generate", "/api/admin", "/api/auth/login", "/api/jobs"]:
            assert client.post(path, json={"user_id": "admin"}).status_code == 404
        assert "izo_private" not in r.text
        assert "s3_endpoint" not in r.text


def test_unconfigured_dependencies_are_not_ready():
    assert dependencies_ready(Settings()) is False


def test_production_rejected_until_hardening():
    with pytest.raises(ValidationError):
        Settings(environment="production")


@pytest.mark.parametrize("endpoint", ["file:///tmp/a", "http://u:p@host", "http://x?a=1", "http://x/path", "ftp://x"])
def test_invalid_storage_endpoint(endpoint):
    with pytest.raises(ValidationError):
        Settings(s3_endpoint=endpoint)


def test_secret_values_are_redacted():
    config = Settings(pg_password="private-database-password", s3_secret_key="private-s3-key")
    assert "private-database-password" not in repr(config)
    assert "private-s3-key" not in config.model_dump_json()


def make_job(executor=Executor.API, modality=Modality.IMAGE):
    return JobSpec(id=uuid4(), owner_id=uuid4(), idempotency_key="example-key-001",
                   capability_id="image.first", modality=modality, executor=executor,
                   provider_id="test-provider", model_id="test-model")


@pytest.mark.parametrize("executor,modality", itertools.product(Executor, Modality))
def test_independent_worker_pools(executor, modality):
    assert pool_for(make_job(executor, modality)) == f"{executor.value}:{modality.value}"


@pytest.mark.parametrize("current,target", itertools.product(JobState, JobState))
def test_transition_graph(current, target):
    if target in ALLOWED[current]:
        assert transition(current, target) == target
    else:
        with pytest.raises(ValueError):
            transition(current, target)


def test_no_blind_retry_after_ambiguous_provider_result():
    assert JobState.QUEUED not in ALLOWED[JobState.RECONCILING]
    assert JobState.CANCELLED not in ALLOWED[JobState.RUNNING]


def test_job_contract_rejects_extra_fields_and_negative_money():
    data = make_job().model_dump()
    with pytest.raises(ValidationError):
        JobSpec(**data, api_key="not-allowed")
    data["reserved_credits"] = -1
    with pytest.raises(ValidationError):
        JobSpec(**data)


def capability(executor=Executor.API):
    return Capability(id="image.first", modality=Modality.IMAGE, enabled=True,
                      provider_id="test-provider", model_id="test-model", executor=executor)


def test_api_selection_does_not_depend_on_local_machine():
    c = capability()
    assert resolve_capability([c], c.id, local_available=False) == c


def test_local_unavailable_does_not_fallback_to_paid_api():
    c = capability(Executor.LOCAL)
    with pytest.raises(ValueError):
        resolve_capability([c], c.id, local_available=False)


def test_duplicate_or_disabled_capability_is_rejected():
    c = capability()
    for catalog in [[], [c, c], [c.model_copy(update={"enabled": False})]]:
        with pytest.raises(ValueError):
            resolve_capability(catalog, c.id, local_available=True)


@pytest.mark.parametrize("key", ["../secrets", "/etc/passwd", "assets/a/b/f", "https://example.org/a", "assets/" + "a"*32 + "/" + "b"*32 + "/a..txt"])
def test_storage_rejects_invalid_keys(key):
    with pytest.raises(ValueError):
        validate_key(key)


def test_private_object_key():
    key = f"assets/{uuid4().hex}/{uuid4().hex}/image.webp"
    assert validate_key(key) == key


def test_storage_health_does_not_return_provider_error():
    class BadClient:
        def head_bucket(self, **kwargs):
            raise RuntimeError("private-config-details")
    store = S3Store.__new__(S3Store)
    store.bucket = "test"
    store.client = BadClient()
    assert not store.healthy()


def test_bootstrap_preserves_existing_credentials(tmp_path):
    path = tmp_path / ".env"
    assert bootstrap(path)
    before = path.read_bytes()
    assert not bootstrap(path)
    assert path.read_bytes() == before
    assert b"IZO_PG_PASSWORD=" in before


def test_openapi_response_matches_generated_artifact():
    encoded = Path("packages/contracts/openapi.json.gz.b64").read_text(encoding="ascii")
    compressed = base64.b64decode("".join(encoded.split()), validate=True)
    exported = json.loads(gzip.decompress(compressed))
    actual = create_app(Settings()).openapi()
    assert exported == actual

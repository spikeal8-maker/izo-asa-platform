"""File-scope/security invariants plus the real bounded S3 adapter, no network."""
import ast
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from izo.media.objects import MediaStore

ROOT = Path(__file__).resolve().parents[1]
KEY = 'assets/' + 'a'*32 + '/' + 'b'*32 + '/image.png'


def adapter(data, declared):
    body = io.BytesIO(data)
    def get_object(**kw):
        assert kw == {'Bucket': 'private-test', 'Key': KEY}
        return {'Body': body, 'ContentLength': declared}
    store = object.__new__(MediaStore)
    store.bucket = 'private-test'
    store.client = SimpleNamespace(get_object=get_object)
    return store, body


def test_s3_adapter_closes_body_and_enforces_real_limit():
    store, body = adapter(b'12345', 5)
    assert store.read(KEY, 5) == b'12345' and body.closed
    store, body = adapter(b'123456', 5)
    with pytest.raises(ValueError):
        store.read(KEY, 5)
    assert body.closed
    store, body = adapter(b'12345', 10)
    with pytest.raises(ValueError):
        store.read(KEY, 5)
    assert body.closed


@pytest.mark.parametrize('maximum', [0, -1, True, 3.5, 100_000_000])
def test_s3_adapter_rejects_unbounded_reads(maximum):
    store, body = adapter(b'123', 3)
    with pytest.raises(ValueError):
        store.read(KEY, maximum)
    assert not body.closed  # No S3 call was made.
    body.close()


def test_s3_adapter_rejects_untrusted_key():
    store, body = adapter(b'123', 3)
    with pytest.raises(ValueError):
        store.read('../private', 3)
    body.close()


def test_media_never_mutates_credits_or_implements_another_identity():
    root = ROOT/'apps/api/izo/media'
    for path in root.glob('*.py'):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(value in (node.module or '') for value in ('credits', 'providers', 'admin'))
        assert 'verify_password(' not in source and 'CreditService(' not in source
        assert 'public-read' not in source and 'generate_presigned_url' not in source


def test_migration_is_static_and_live_acceptance_is_wired():
    source = (ROOT/'apps/api/migrations/versions/0007_media.py').read_text()
    assert 'izo.media' not in source and '0006_admin' in source
    workflow = (ROOT/'.github/workflows/ci.yml').read_text()
    assert workflow.index('tools/media_acceptance.py before') < workflow.index('docker compose down\n')
    assert workflow.index('tools/media_acceptance.py after') > workflow.index('docker compose up --wait')
    assert 'IZO_MEDIA_ACCEPTANCE=isolated' in workflow and 'umask 077' in workflow
    assert workflow.count('rm -f "$RUNNER_TEMP/izo-media-state.json"') == 2
    assert 'Pillow==12.3.0' in (ROOT/'requirements.in').read_text()
    assert 'Pillow==12.3.0' in (ROOT/'requirements.lock').read_text()
    script = (ROOT/'tools/media_acceptance.py').read_text()
    assert 'set_default(' not in script  # Fixtures cannot alter the existing baseline plan.
    assert 'DISABLE TRIGGER' not in script and 'TRUNCATE' not in script


def test_incremental_media_pr_keeps_both_ci_gates():
    for name in ("ci.yml", "dependency-audit.yml"):
        text = (ROOT / ".github/workflows" / name).read_text()
        assert "  pull_request: {}" in text  # All bases include the original media stack.
        assert "contents: read" in text and "persist-credentials: false" in text
        assert "pull_request_target" not in text and "self-hosted" not in text
        assert "continue-on-error" not in text and "secrets." not in text

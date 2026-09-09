"""IMAGE-001 cross-layer guards. Browser tests own behavior; these guard wiring."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'apps/web'


def test_main_workspace_has_no_demo_wallet_or_fake_provider():
    app = (WEB / 'src/shell/App.tsx').read_text()
    assert 'DemoProvider' not in app and 'useDemo' not in app
    assert not list((WEB / 'src/features/prototype').glob('*.ts*'))
    for name in ('studio/Studio.tsx', 'studio/ResultPanel.tsx', 'gallery/Gallery.tsx', 'gallery/AssetPage.tsx'):
        text = (WEB / 'src/features' / name).read_text()
        assert 'WorkspaceGate' in text
        assert 'useDemo' not in text
        assert not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(', text)


def test_pending_command_is_owner_scoped_and_has_no_credentials_or_pixels():
    text = (WEB / 'src/shared/submission.ts').read_text()
    assert 'izo-pending-submit:${owner}' in text and 'value.owner !== owner' in text
    assert 'crypto.randomUUID()' in text and 'saved.operation_id' in text
    assert 'operation_id,owner,quote_id,version' in text
    studio = (WEB / 'src/features/studio/Studio.tsx').read_text()
    assert studio.index('remember(auth.account.id') < studio.index("apiRequest<Job>('/api/v1/jobs'")
    assert 'command.quote_id' in studio and 'command.operation_id' in studio
    assert 'active.current' in studio


def test_media_read_uses_fresh_ticket_and_bounded_authenticated_transport():
    transport = (WEB / 'src/shared/api.ts').read_text()
    assert "credentials: 'same-origin'" in transport and "redirect: 'error'" in transport
    assert 'total > byteSize' in transport and 'total !== byteSize' in transport
    assert 'hash !== expectedHash' in transport
    preview = (WEB / 'src/features/gallery/PrivateImage.tsx').read_text()
    assert 'URL.revokeObjectURL' in preview and 'controller.abort()' in preview
    detail = (WEB / 'src/features/gallery/AssetPage.tsx').read_text()
    assert 'await downloadTicket(asset, auth)' in detail
    gallery = (WEB / 'src/features/gallery/Gallery.tsx').read_text()
    assert 'imageBlob(' not in gallery and 'downloadTicket(' not in gallery


def test_session_loss_and_polling_have_cleanup_not_global_private_cache():
    text = (WEB / 'src/shared/workspace.tsx').read_text()
    assert 'izo:session-invalid' in text and 'setAuth(null)' in text
    assert 'controller.abort()' in text and 'clearTimeout(timer)' in text
    assert "sessionStorage" not in text and "localStorage" not in text
    assert 'poll?.(value)' in text


def test_real_browser_acceptance_does_not_mock_the_platform():
    text = (WEB / 'acceptance/image-live.mjs').read_text()
    assert 'route.fulfill' not in text and 'page.routeFromHAR' not in text
    for item in ('IMAGE_BROWSER_BEFORE_OK', 'IMAGE_BROWSER_AFTER_OK', 'izo.jobs.worker',
                 "name: 'Подтвердить создание'", 'downloadedHash', 'state.other'):
        assert item in text
    assert "IZO_IMAGE_ACCEPTANCE !== 'isolated'" in text
    assert "process.env.IZO_ENVIRONMENT !== 'test'" in text
    assert 'page.screenshot' in text and 'state.browser.sha256' in text


def test_image_acceptance_retains_every_previous_restart_gate():
    text = (ROOT / '.github/workflows/ci.yml').read_text()
    assert text.index('tools/image_acceptance.py before') < text.index('tools/jobs_acceptance.py before')
    assert text.index('tools/image_acceptance.py after') > text.index('tools/jobs_acceptance.py after')
    assert text.count('rm -f "$RUNNER_TEMP/izo-image-state.json"') == 2
    assert 'image-live.mjs "$RUNNER_TEMP/izo-image-state.json" before' in text
    assert 'image-live.mjs "$RUNNER_TEMP/izo-image-state.json" after' in text
    for name in ('auth', 'email', 'credit', 'entitlement', 'admin', 'media', 'jobs'):
        assert f'tools/{name}_acceptance.py before' in text
        assert f'tools/{name}_acceptance.py after' in text
    assert 'admin-live.mjs' in text and 'npm run test:e2e' in text
    assert 'contents: read' in text and 'continue-on-error' not in text


def test_review_source_archives_only_git_tracked_tree_not_runtime_directory():
    text = (ROOT / '.github/workflows/review-source.yml').read_text()
    assert 'git archive --format=tar HEAD' in text and 'git ls-tree -r -z HEAD' in text
    assert 'contents: read' in text and 'persist-credentials: false' in text
    assert 'tar -czf' not in text and 'secrets.' not in text and 'npm' not in text
    assert 'sha256sum source.tar.gz' in text


def test_scope_is_finite_and_keeps_backend_business_code_unchanged():
    value = json.loads((ROOT / 'tools/scopes/image-001.json').read_text())
    assert value['max_files'] == 34 and len(value['allowed']) <= 34
    assert value['base'] == 'cab337ddd2dc6a573b4a5366b071d31e26bd0523'
    assert not any(path.startswith('apps/api/') for path in value['allowed'])
    assert 'requirements.lock' not in value['allowed'] and 'apps/web/package-lock.json' not in value['allowed']

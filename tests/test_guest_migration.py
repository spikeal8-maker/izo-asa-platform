"""GUEST-001 migration stays additive, bounded and forward-only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'apps/api/migrations/versions/0011_guest.py'


def test_guest_migration_follows_access_and_owns_only_guest_session_schema():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'revision = "0011_guest"' in text
    assert 'down_revision = "0010_access"' in text
    assert 'op.create_table("guest_sessions"' in text
    assert 'sa.ForeignKey("accounts.id", ondelete="CASCADE")' in text
    assert 'trial_operation_id' in text and 'claimed_at' in text
    assert 'credit_entry_movement' in text and "kind = 'trial'" in text
    assert "reason = 'guest_trial'" in text
    assert 'raise RuntimeError' in text
    for forbidden in ('generation_jobs', 'media_assets', 'provider_calls', 'staff_access_grants'):
        assert f'op.create_table("{forbidden}"' not in text


def test_guest_migration_has_no_secret_provider_or_external_io_surface():
    text = MIGRATION.read_text(encoding='utf-8').lower()
    for forbidden in ('fal.ai', 'openrouter', 'http://', 'https://', 'secret_key', 'api_key'):
        assert forbidden not in text

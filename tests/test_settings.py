"""SETTINGS-002 lifecycle on current Entitlements storage and ACCESS provisioning."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.access.schemas import GrantAccessInput
from izo.access.service import AccessService
from izo.entitlements import tables as ent
from izo.entitlements.schemas import ImageSize, PlanPolicy
from izo.settings.schemas import PreviewInput, PublishInput, RollbackInput, SettingsError
from izo.settings.service import SettingsService
from test_admin import admin_env, password_hash, PASSWORD


def valid_policy(**changes):
    values = dict(capability_ids=("test.image.v1",), executors=("api",), active_jobs=2,
        submissions=10, window_seconds=60, storage_bytes=1_000_000, upload_bytes=0,
        input_count=0, image_sizes=(ImageSize(width=64, height=64),),
        max_action_credits=1, can_publish=False)
    values.update(changes)
    return PlanPolicy(**values)

@pytest.fixture
def settings_env(admin_env):
    admin, users, sessions = admin_env
    access = AccessService(admin.auth)
    access.enroll_local_owner(users[0])
    for permission in ("plans.read", "plans.write"):
        access.grant(sessions[0].bearer, sessions[0].view.csrf_token, users[2],
            GrantAccessInput(operation_id=uuid4(), permission=permission, scope="global",
                ttl_seconds=3600, case_reference="SETTINGS-"+uuid4().hex,
                current_password=PASSWORD), "fixture")
    with admin.auth.engine.begin() as conn:
        conn.execute(sa.insert(ent.defaults).values(id=1, version=0))
    return SettingsService(admin.auth), access, users, sessions


def publish(env, expected, policy=None, operation=None, who=2):
    service, _, _, sessions = env
    data = PublishInput(operation_id=operation or uuid4(), expected_revision=expected,
        policy=policy or valid_policy(), reason="settings acceptance fixture")
    return service.publish(sessions[who].bearer, sessions[who].view.csrf_token, data), data


def test_access_provisioning_materializes_settings_permissions(settings_env):
    _, access, users, sessions = settings_env
    card = access.subject(sessions[0].bearer, users[2])
    managed = {item.permission for item in card.permissions if item.managed}
    assert {"plans.read", "plans.write"} <= managed

def test_read_requires_plans_read(settings_env):
    service, _, _, sessions = settings_env
    with pytest.raises(Exception) as exc:
        service.view(sessions[1].bearer)
    assert getattr(exc.value, "code", None) == "forbidden"


def test_empty_default_is_explicit_deny_and_descriptors_are_complete(settings_env):
    service, _, _, sessions = settings_env
    view = service.view(sessions[2].bearer)
    assert view.default_version == 0 and view.revision_id is None
    assert not view.generation_enabled and view.policy.capability_ids == ()
    ids = {item.id for item in view.descriptors}
    assert {"S-10","S-11","S-12","S-13","S-14","S-15","S-17","S-22","P-01"} <= ids
    assert next(item for item in view.descriptors if item.id == "P-01").key == "plan.max_action_credits"


def test_preview_is_read_only_diff_and_impact(settings_env):
    service, _, _, sessions = settings_env
    preview = service.preview(sessions[2].bearer,
        PreviewInput(expected_revision=0, policy=valid_policy()))
    assert preview.current_revision == 0 and preview.generation_enabled
    assert "plan.capability_ids" in {item.key for item in preview.diff}
    assert preview.missing_required == ()
    assert any("accepted jobs" in item for item in preview.impact)
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(ent.revisions)).scalar_one() == 0

@pytest.mark.parametrize("change,missing", [
    ({"executors": ()}, "plan.executor_types"),
    ({"active_jobs": 0}, "plan.active_jobs"),
    ({"submissions": 0}, "plan.submission_window.limit"),
    ({"storage_bytes": 0}, "plan.storage_bytes"),
    ({"image_sizes": ()}, "plan.image_sizes"),
    ({"max_action_credits": 0}, "plan.max_action_credits"),
])
def test_required_fields_block_enabled_generation(settings_env, change, missing):
    service, _, _, sessions = settings_env
    policy = valid_policy(**change)
    preview = service.preview(sessions[2].bearer,
        PreviewInput(expected_revision=0, policy=policy))
    assert missing in preview.missing_required and not preview.generation_enabled
    with pytest.raises(SettingsError, match="required_setting_missing") as exc:
        publish(settings_env, 0, policy)
    assert missing in exc.value.fields


def test_deny_all_policy_can_be_published_safely(settings_env):
    service, _, _, sessions = settings_env
    receipt, _ = publish(settings_env, 0, PlanPolicy())
    assert receipt.default_version == 1
    assert not service.view(sessions[2].bearer).generation_enabled

def test_publish_exact_retry_is_one_revision_and_one_default_change(settings_env):
    service, _, _, sessions = settings_env
    operation = uuid4()
    first, data = publish(settings_env, 0, operation=operation)
    second = service.publish(sessions[2].bearer, sessions[2].view.csrf_token, data)
    assert second == first and first.default_version == 1 and first.revision == 1
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(ent.revisions)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(ent.changes)).scalar_one() == 2


def test_changed_payload_with_same_operation_is_rejected(settings_env):
    operation = uuid4()
    first, data = publish(settings_env, 0, operation=operation)
    changed = data.model_copy(update={"policy": valid_policy(active_jobs=3)})
    service, _, _, sessions = settings_env
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        service.publish(sessions[2].bearer, sessions[2].view.csrf_token, changed)
    assert first.revision == 1


def test_expected_revision_conflict_does_not_create_revision(settings_env):
    publish(settings_env, 0)
    with pytest.raises(SettingsError, match="revision_conflict"):
        publish(settings_env, 0, valid_policy(active_jobs=3))
    service = settings_env[0]
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(ent.revisions)).scalar_one() == 1

def test_rollback_creates_new_revision_without_rewriting_history(settings_env):
    service, _, _, sessions = settings_env
    first, _ = publish(settings_env, 0, valid_policy(active_jobs=2))
    second, _ = publish(settings_env, 1, valid_policy(active_jobs=5))
    rolled = service.rollback(sessions[2].bearer, sessions[2].view.csrf_token,
        RollbackInput(operation_id=uuid4(), expected_revision=2,
            target_revision=first.revision, reason="restore reviewed limits"))
    current = service.view(sessions[2].bearer)
    history = service.history(sessions[2].bearer)
    assert rolled.action == "rollback" and rolled.revision > second.revision
    assert current.policy.active_jobs == 2 and current.default_version == 3
    assert [item.revision for item in history.items][:3] == [rolled.revision, second.revision, first.revision]
    assert sum(item.active for item in history.items) == 1


def test_unknown_field_and_cross_field_policy_fail_before_write(settings_env):
    with pytest.raises(ValidationError):
        PreviewInput.model_validate({"expected_revision": 0, "policy": {
            **valid_policy().model_dump(mode="json"), "surprise": True}})
    with pytest.raises(ValidationError):
        valid_policy(storage_bytes=10, upload_bytes=11)
    service = settings_env[0]
    with service.auth.engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(ent.revisions)).scalar_one() == 0

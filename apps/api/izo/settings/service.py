"""Canonical basic PlanPolicy lifecycle; no provider settings, secrets or second settings store."""
from uuid import UUID, uuid5

import sqlalchemy as sa

from ..accounts.admin_access import staff_session
from ..entitlements import tables as ent_tables
from ..entitlements.schemas import PlanPolicy, PublishPlan, SetDefault, EntitlementError
from ..entitlements.service import EntitlementService
from .schemas import (BasicSettingsView, DiffItem, HistoryItem, HistoryView, PreviewInput,
                      PreviewView, PublishInput, PublishReceipt, RollbackInput,
                      SettingDescriptor, SettingsError)

DESCRIPTORS = (
    SettingDescriptor(id="S-10", key="plan.capability_ids", value_type="set<capability>",
        required_when_generation_enabled=True, default_semantics="empty = deny all capabilities"),
    SettingDescriptor(id="S-11", key="plan.executor_types", value_type="set<api|local>",
        required_when_generation_enabled=True, default_semantics="empty = no executor"),
    SettingDescriptor(id="S-12", key="plan.active_jobs", value_type="int 0..256",
        required_when_generation_enabled=True, default_semantics="0 = deny new jobs"),
    SettingDescriptor(id="S-13", key="plan.submission_window", value_type="limit + window_seconds",
        required_when_generation_enabled=True, default_semantics="0 submissions = deny"),
    SettingDescriptor(id="S-14", key="plan.storage_bytes", value_type="bytes",
        required_when_generation_enabled=True, default_semantics="0 = no new storage"),
    SettingDescriptor(id="S-15", key="plan.upload_limits", value_type="bytes + input_count",
        required_when_generation_enabled=False, default_semantics="0 = uploads disabled"),
    SettingDescriptor(id="S-17", key="plan.image_sizes", value_type="set<width,height>",
        required_when_generation_enabled=True, default_semantics="empty = no image size"),
    SettingDescriptor(id="S-22", key="plan.publishing", value_type="bool",
        required_when_generation_enabled=False, default_semantics="false = private only"),
    SettingDescriptor(id="P-01", key="plan.max_action_credits", value_type="credits 0..1000000000",
        required_when_generation_enabled=True, default_semantics="0 = deny credit-consuming actions"),
)

FIELD_KEYS = {
    "capability_ids": "plan.capability_ids", "executors": "plan.executor_types",
    "active_jobs": "plan.active_jobs", "submissions": "plan.submission_window.limit",
    "window_seconds": "plan.submission_window.window_seconds", "storage_bytes": "plan.storage_bytes",
    "upload_bytes": "plan.upload_limits.max_file_bytes", "input_count": "plan.upload_limits.max_inputs",
    "image_sizes": "plan.image_sizes", "max_action_credits": "plan.max_action_credits",
    "can_publish": "plan.publishing.can_publish",
}


class SettingsService:
    def __init__(self, auth):
        self.auth = auth
        self.entitlements = EntitlementService(clock=auth.clock)

    @staticmethod
    def _policy(row) -> PlanPolicy:
        return PlanPolicy.model_validate_json(row["policy_json"]) if row else PlanPolicy()

    def _current(self, conn, *, lock=False):
        query = sa.select(ent_tables.defaults).where(ent_tables.defaults.c.id == 1)
        if lock:
            query = query.with_for_update()
        default = conn.execute(query).mappings().first()
        if default is None:
            raise SettingsError(503, "policy_unavailable")
        row = None
        if default["revision_id"] is not None:
            row = conn.execute(sa.select(ent_tables.revisions).where(
                ent_tables.revisions.c.id == default["revision_id"])).mappings().first()
            if row is None or row["plan_code"] != "basic":
                raise SettingsError(503, "invalid_policy")
        return default, row, self._policy(row)

    @staticmethod
    def _missing(policy: PlanPolicy) -> tuple[str, ...]:
        if not policy.capability_ids:
            return ()
        missing = []
        if not policy.executors:
            missing.append("plan.executor_types")
        if policy.active_jobs == 0:
            missing.append("plan.active_jobs")
        if policy.submissions == 0:
            missing.append("plan.submission_window.limit")
        if policy.storage_bytes == 0:
            missing.append("plan.storage_bytes")
        if not policy.image_sizes:
            missing.append("plan.image_sizes")
        if policy.max_action_credits == 0:
            missing.append("plan.max_action_credits")
        return tuple(missing)

    @staticmethod
    def _diff(before: PlanPolicy, after: PlanPolicy) -> tuple[DiffItem, ...]:
        old = before.model_dump(mode="json")
        new = after.model_dump(mode="json")
        return tuple(DiffItem(key=FIELD_KEYS[name], before=old[name], after=new[name])
                     for name in old if old[name] != new[name])

    def view(self, raw) -> BasicSettingsView:
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"plans.read"})
            default, row, policy = self._current(conn)
            return BasicSettingsView(default_version=default["version"],
                revision_id=row["id"] if row else None, revision=row["revision"] if row else None,
                policy_hash=row["policy_hash"] if row else None, policy=policy,
                generation_enabled=bool(policy.capability_ids) and not self._missing(policy),
                descriptors=DESCRIPTORS)

    def preview(self, raw, data: PreviewInput) -> PreviewView:
        data = PreviewInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"plans.read"})
            default, _, current = self._current(conn)
            if default["version"] != data.expected_revision:
                raise SettingsError(409, "revision_conflict")
            missing = self._missing(data.policy)
            return PreviewView(expected_revision=data.expected_revision,
                current_revision=default["version"], diff=self._diff(current, data.policy),
                generation_enabled=bool(data.policy.capability_ids) and not missing,
                missing_required=missing,
                impact=("new quotes and jobs use the new revision",
                        "accepted jobs retain their execution and plan snapshots",
                        "credits, existing files and ledger history are not rewritten"))

    def _existing_publish(self, conn, operation_id: UUID):
        publish_id = uuid5(operation_id, "settings-publish")
        change = conn.execute(sa.select(ent_tables.changes).where(
            ent_tables.changes.c.operation_id == publish_id)).mappings().first()
        if not change or change["revision_id"] is None:
            return None
        return conn.execute(sa.select(ent_tables.revisions).where(
            ent_tables.revisions.c.id == change["revision_id"])).mappings().one()

    def _publish(self, raw, csrf, data: PublishInput, action: str) -> PublishReceipt:
        data = PublishInput.model_validate(data)
        missing = self._missing(data.policy)
        if data.policy.capability_ids and missing:
            raise SettingsError(422, "required_setting_missing", missing)
        publish_id = uuid5(data.operation_id, "settings-publish")
        default_id = uuid5(data.operation_id, "settings-default")
        revision_id = uuid5(data.operation_id, "settings-revision")
        with self.auth.engine.begin() as conn:
            account, _, _ = staff_session(self.auth, conn, raw, {"plans.write"},
                                           csrf=csrf, mutation=True)
            existing = self._existing_publish(conn, data.operation_id)
            if existing is not None:
                revision_id = existing["id"]
                revision_number = existing["revision"]
            else:
                default, _, _ = self._current(conn, lock=True)
                if default["version"] != data.expected_revision:
                    raise SettingsError(409, "revision_conflict")
                revision_number = int(conn.execute(sa.select(sa.func.coalesce(
                    sa.func.max(ent_tables.revisions.c.revision), 0)).where(
                    ent_tables.revisions.c.plan_code == "basic")).scalar_one()) + 1
            try:
                self.entitlements.publish(conn, account["id"], PublishPlan(
                    operation_id=publish_id, revision_id=revision_id, plan_code="basic",
                    revision=revision_number, policy=data.policy, reason=data.reason))
                receipt = self.entitlements.set_default(conn, account["id"], SetDefault(
                    operation_id=default_id, revision_id=revision_id,
                    expected_version=data.expected_revision, reason=data.reason))
            except EntitlementError as exc:
                raise SettingsError(exc.status, exc.code) from None
            row = conn.execute(sa.select(ent_tables.revisions).where(
                ent_tables.revisions.c.id == revision_id)).mappings().one()
            return PublishReceipt(operation_id=data.operation_id,
                default_version=receipt.version, revision_id=revision_id,
                revision=row["revision"], policy_hash=row["policy_hash"], action=action)

    def publish(self, raw, csrf, data: PublishInput) -> PublishReceipt:
        return self._publish(raw, csrf, data, "publish")

    def rollback(self, raw, csrf, data: RollbackInput) -> PublishReceipt:
        data = RollbackInput.model_validate(data)
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"plans.write"}, csrf=csrf, mutation=True)
            row = conn.execute(sa.select(ent_tables.revisions).where(
                ent_tables.revisions.c.plan_code == "basic",
                ent_tables.revisions.c.revision == data.target_revision)).mappings().first()
            if row is None:
                raise SettingsError(404, "revision_not_found")
            policy = self._policy(row)
        return self._publish(raw, csrf, PublishInput(operation_id=data.operation_id,
            expected_revision=data.expected_revision, policy=policy,
            reason=data.reason), "rollback")

    def history(self, raw, limit=20) -> HistoryView:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise SettingsError(422, "invalid_pagination")
        with self.auth.engine.begin() as conn:
            staff_session(self.auth, conn, raw, {"plans.read"})
            default, _, _ = self._current(conn)
            rows = conn.execute(sa.select(ent_tables.revisions).where(
                ent_tables.revisions.c.plan_code == "basic").order_by(
                ent_tables.revisions.c.revision.desc()).limit(limit)).mappings().all()
            return HistoryView(items=tuple(HistoryItem(revision_id=row["id"],
                revision=row["revision"], policy_hash=row["policy_hash"],
                created_at=row["created_at"], active=row["id"] == default["revision_id"],
                policy=self._policy(row)) for row in rows))

"""Versioned plans; no billing mutations, API-provider calls or auto grants.

Internal administrative commands require a server-resolved actor and plans.write.
They are deliberately NOT exposed as HTTP mutations or a privileged public CLI.
"""
import time
from uuid import UUID
import sqlalchemy as sa

from ..accounts import entitlement_access as access
from ..credits.service import CreditService
from . import repository as repo, tables as t
from .schemas import (AssignPlan, PublishPlan, SetDefault, EntitlementView,
                      EntitlementError)
from .policy import evaluate


class EntitlementService:
    def __init__(self, clock=time.time):
        self.clock = clock

    def now(self):
        return int(self.clock())

    def _authorize(self, conn, actor, target=None):
        ids = [actor] if target is None else [actor, target]
        states = access.locked_states(conn, ids)
        if any(value not in states for value in ids):
            raise EntitlementError(404, "not_found")
        if states[actor] != "active" or not access.may_write(conn, actor, self.now()):
            raise EntitlementError(403, "plan_write_forbidden")
        if target is not None and states[target] not in {"active", "generation_suspended"}:
            raise EntitlementError(403, "account_restricted")

    def publish(self, conn, actor: UUID, command: PublishPlan):
        command = PublishPlan.model_validate(command)
        with repo.atomic(conn):
            self._authorize(conn, actor)
            fingerprint = repo.fingerprint("publish", actor, None, command)
            old = repo.replay(conn, command.operation_id, fingerprint)
            if old is not None:
                return old
            data = repo.canonical(command.policy.model_dump(mode="json"))
            conn.execute(sa.insert(t.revisions).values(id=command.revision_id,
                plan_code=command.plan_code, revision=command.revision, policy_json=data,
                policy_hash=repo.digest(data), created_at=self.now()))
            return repo.record(conn, actor, None, "publish", command, fingerprint,
                               command.revision, self.now())

    def set_default(self, conn, actor: UUID, command: SetDefault):
        command = SetDefault.model_validate(command)
        with repo.atomic(conn):
            self._authorize(conn, actor)
            row = conn.execute(sa.select(t.defaults).where(t.defaults.c.id == 1)
                               .with_for_update()).mappings().first()
            if row is None:
                raise EntitlementError(503, "policy_unavailable")
            fingerprint = repo.fingerprint("default", actor, None, command)
            old = repo.replay(conn, command.operation_id, fingerprint)
            if old is not None:
                return old
            self._version(row["version"], command.expected_version)
            revision, _ = repo.revision(conn, command.revision_id)
            if revision["plan_code"] != "basic":
                raise EntitlementError(422, "basic_default_required")
            version = row["version"] + 1
            conn.execute(sa.update(t.defaults).where(t.defaults.c.id == 1)
                         .values(revision_id=command.revision_id, version=version))
            return repo.record(conn, actor, None, "default", command, fingerprint,
                               version, self.now())

    def assign(self, conn, actor: UUID, account_id: UUID, command: AssignPlan):
        command = AssignPlan.model_validate(command)
        with repo.atomic(conn):
            self._authorize(conn, actor, account_id)
            fingerprint = repo.fingerprint("assign", actor, account_id, command)
            old = repo.replay(conn, command.operation_id, fingerprint)
            if old is not None:
                return old
            current = conn.execute(sa.select(t.assignments).where(
                t.assignments.c.account_id == account_id).with_for_update()).mappings().first()
            version = current["version"] if current else 0
            self._version(version, command.expected_version)
            if command.revision_id is not None:
                repo.revision(conn, command.revision_id)
            values = dict(revision_id=command.revision_id, starts_at=command.starts_at,
                          expires_at=command.expires_at, version=version + 1)
            if current is None:
                conn.execute(sa.insert(t.assignments).values(account_id=account_id, **values))
            else:
                conn.execute(sa.update(t.assignments).where(
                    t.assignments.c.account_id == account_id).values(**values))
            return repo.record(conn, actor, account_id, "assign", command, fingerprint,
                               version + 1, self.now())

    @staticmethod
    def _version(current, expected):
        if current != expected or current >= 2_000_000_000:
            raise EntitlementError(409, "revision_conflict")

    def resolve(self, conn, account_id: UUID) -> EntitlementView:
        """Internal ID from validated identity. No wallet writes or hidden expiry jobs."""
        with repo.atomic(conn):
            states = access.locked_states(conn, [account_id])
            if account_id not in states:
                raise EntitlementError(404, "not_found")
            if states[account_id] not in {"active", "generation_suspended"}:
                raise EntitlementError(403, "account_restricted")
            # Shared configuration lock, AFTER Accounts, prevents torn selection.
            default = conn.execute(sa.select(t.defaults).where(t.defaults.c.id == 1)
                .with_for_update(read=True)).mappings().first()
            if default is None:
                raise EntitlementError(503, "policy_unavailable")
            assignment = conn.execute(sa.select(t.assignments).where(
                t.assignments.c.account_id == account_id)).mappings().first()
            now = self.now()
            selected, source = default["revision_id"], "basic"
            state, next_change = "none", None
            if assignment and assignment["revision_id"] is not None:
                if assignment["expires_at"] is not None and assignment["expires_at"] <= now:
                    state = "expired"
                elif assignment["starts_at"] > now:
                    state, next_change = "scheduled", assignment["starts_at"]
                else:
                    state, selected, source = "active", assignment["revision_id"], "assignment"
                    next_change = assignment["expires_at"]
            row, policy = repo.revision(conn, selected) if selected else (None, None)
            if row and source == "basic" and row["plan_code"] != "basic":
                raise EntitlementError(503, "invalid_policy")
            return EntitlementView(account_id=account_id, account_state=states[account_id],
                identity_verified=access.verified(conn, account_id), configured=row is not None,
                source=source if row else "none", assignment_state=state,
                assignment_version=assignment["version"] if assignment else 0,
                default_version=default["version"], revision_id=selected,
                plan_code=row["plan_code"] if row else None, revision=row["revision"] if row else None,
                policy_hash=row["policy_hash"] if row else None, policy=policy,
                as_of=now, next_change_at=next_change)

    def assess_image(self, conn, account_id: UUID, demand, runtime, usage=None):
        """Read-only preflight, NOT a reservation. Missing usage fails closed.

        JOBS/MEDIA will supply owner-locked usage with matching timestamp/window
        and reserve resources + credits + job in this same outer transaction.
        Never expose this method with client-supplied usage/provider booleans.
        """
        with repo.atomic(conn):
            view = self.resolve(conn, account_id)
            balance = CreditService(clock=self.clock).overview(conn, account_id, limit=1).balance
            return evaluate(view, demand, runtime, usage, balance.available)

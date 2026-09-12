"""Small administrative application service; Credits is the only money writer."""
from contextlib import contextmanager
from uuid import UUID, uuid4
from sqlalchemy.exc import IntegrityError
import sqlalchemy as sa

from ..accounts import admin_access as access
from ..accounts.security import AuthError
from ..credits.schemas import CreditError, Grant, MAX_OPERATION
from ..credits.service import CreditService
from . import tables as t
from .schemas import (AdminAccess, AdminUsers, AdminUser, AdminEvent, AdminEvents,
                      CompensationInput, CompensationReceipt)

STAFF = ("users.read_limited", "credits.read", "credits.grant", "audit.read", "access.read")


class AdminService:
    def __init__(self, auth):
        self.auth = auth
        self.credits = CreditService(auth.clock)

    def _event(self, conn, actor, action, *, target=None, outcome="success",
               reference=None, operation=None, entry=None):
        conn.execute(sa.insert(t.events).values(id=uuid4(), actor_id=actor,
            target_id=target, action=action, outcome=outcome, case_reference=reference,
            operation_id=operation, entry_id=entry, created_at=self.auth.now()))

    @contextmanager
    def _action(self, raw, name, target=None):
        try:
            with self.auth.engine.begin() as conn:
                yield conn
        except IntegrityError as error:
            code = getattr(error.orig, "sqlstate", None)
            unique = getattr(error.orig, "sqlite_errorcode", None) in {1555, 2067}
            if code == "23505" or unique:
                raise AuthError(409, "admin_conflict") from None
            raise
        except (AuthError, CreditError) as error:
            # No unbounded unauthenticated audit inserts; revoked/invalid sessions
            # use the existing safe HTTP event. Known denied actors are audited.
            if error.status != 401:
                with self.auth.engine.begin() as conn:
                    try:
                        owner = access.session_owner(conn, raw)
                    except AuthError:
                        owner = None
                    if owner is not None:
                        self._event(conn, owner, name, target=target, outcome="denied")
            raise

    def _limit(self, conn, actor):
        row = conn.execute(sa.select(t.policies).where(t.policies.c.account_id == actor)
                           .with_for_update()).mappings().first()
        if not row or (row["expires_at"] is not None and row["expires_at"] <= self.auth.now()):
            return 0
        return row["max_grant"]

    def me(self, raw):
        with self._action(raw, "admin.access") as conn:
            actor, session, grants = access.staff_session(self.auth, conn, raw, {"users.read_limited"})
            maximum = self._limit(conn, actor["id"]) if {"credits.grant", "credits.read"} <= grants else 0
            return AdminAccess(permissions=sorted(grants.intersection(STAFF)),
                               max_grant=maximum, csrf_token=session["csrf_token"])

    def users(self, raw, query: str, limit=20, after: UUID | None = None):
        if type(limit) is not int or not 1 <= limit <= 50 or not 3 <= len(query.strip()) <= 80:
            raise AuthError(422, "invalid_search")
        with self._action(raw, "users.search") as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw, {"users.read_limited"})
            rows = access.search_users(conn, query.strip(), limit, after)
            result = [AdminUser.model_validate(dict(row)) for row in rows[:limit]]
            self._event(conn, actor["id"], "users.search")  # Search text may contain PII; never log it.
            return AdminUsers(users=result, next_after=result[-1].id if len(rows) > limit else None)

    def user(self, raw, target: UUID):
        with self._action(raw, "users.read", target) as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw, {"users.read_limited"}, target=target)
            result = AdminUser.model_validate(access.user_card(conn, target))
            self._event(conn, actor["id"], "users.read", target=target)
            return result

    def credits_view(self, raw, target: UUID, limit=20, before=None):
        with self._action(raw, "credits.read", target) as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw,
                {"users.read_limited", "credits.read"}, target=target)
            result = self.credits.overview(conn, target, limit=limit, before=before)
            self._event(conn, actor["id"], "credits.read", target=target)
            return result

    def compensate(self, raw, csrf, target: UUID, command: CompensationInput, peer: str):
        # Authenticate again after KDF, in the same transaction as the one ledger command.
        command = CompensationInput.model_validate(command.model_dump())
        try:
            proof = access.reauthenticate(self.auth, raw, csrf,
                                          command.current_password.get_secret_value(), peer)
        except AuthError as exc:
            with self._action(raw, "compensation.grant", target):
                raise exc
        with self._action(raw, "compensation.grant", target) as conn:
            actor, _, _ = access.staff_session(self.auth, conn, raw,
                {"users.read_limited", "credits.read", "credits.grant"},
                target=target, csrf=csrf, mutation=True)
            if actor["id"] != proof.owner_id or actor["password_hash"] != proof.encoded:
                raise AuthError(403, "reauth_required")
            old = conn.execute(sa.select(t.events).where(
                t.events.c.operation_id == command.operation_id)).mappings().first()
            if old and (old["actor_id"] != actor["id"] or old["target_id"] != target
                        or old["case_reference"] != command.case_reference):
                raise AuthError(409, "idempotency_conflict")
            limit = self._limit(conn, actor["id"])
            entry = self.credits.grant(conn, target, actor["id"], Grant(
                operation_id=command.operation_id, case_id=command.case_id(),
                amount=command.amount, reason="compensation"), grant_limit=limit)
            existing = conn.execute(sa.select(t.events.c.id).where(
                t.events.c.operation_id == command.operation_id)).first()
            if existing is None:
                self._event(conn, actor["id"], "compensation.granted", target=target,
                    reference=command.case_reference, operation=command.operation_id, entry=entry.entry_id)
            return CompensationReceipt(account_id=target, case_reference=command.case_reference, entry=entry)

    def audit(self, raw, limit=20, before: UUID | None = None):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise AuthError(422, "invalid_pagination")
        with self._action(raw, "audit.read") as conn:
            access.staff_session(self.auth, conn, raw, {"users.read_limited", "audit.read"})
            query = sa.select(t.events)
            if before:
                cursor = conn.execute(sa.select(t.events.c.created_at).where(
                    t.events.c.id == before)).scalar_one_or_none()
                if cursor is None:
                    raise AuthError(422, "invalid_pagination")
                query = query.where(sa.or_(t.events.c.created_at < cursor,
                    sa.and_(t.events.c.created_at == cursor, t.events.c.id < before)))
            rows = conn.execute(query.order_by(t.events.c.created_at.desc(),
                t.events.c.id.desc()).limit(limit + 1)).mappings().all()
            items = [AdminEvent.model_validate(dict(row)) for row in rows[:limit]]
            return AdminEvents(events=items, next_before=items[-1].id if len(rows) > limit else None)

    def enroll_local_operator(self, target: UUID, max_grant: int):
        """Explicit operator CLI/test only. No public API and no implicit first signup role."""
        if type(max_grant) is not int or not 0 < max_grant <= MAX_OPERATION:
            raise ValueError("Finite positive grant limit required")
        with self.auth.engine.begin() as conn:
            access.enroll_local_operator(conn, target, STAFF, self.auth.now())
            conn.execute(sa.insert(t.policies).values(account_id=target, max_grant=max_grant,
                                                       created_at=self.auth.now()))
            self._event(conn, target, "admin.local_enrollment", target=target)

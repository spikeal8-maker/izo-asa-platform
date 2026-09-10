"""Atomic admission: trusted session -> policy -> quota -> credit hold -> job/outbox."""
import json
from uuid import uuid4, uuid5
import sqlalchemy as sa

from ..accounts import jobs_access as access
from ..credits.service import CreditService
from ..credits.schemas import Reserve, Release
from ..entitlements.service import EntitlementService
from ..entitlements.policy import ImageDemand, ImageSize, RuntimeState, UsageSnapshot, evaluate
from ..media import repository as media_repo, outputs
from . import catalog, repository as repo, tables as t
from .schemas import QuoteInput, QuoteView, CreateJob, JobError, JobList, ACTIVE, TERMINAL
from ..providers.openrouter.config import OpenRouterSettings


class JobService:
    def __init__(self, auth, policy=None, openrouter=None):
        self.auth = auth
        self.policy = policy if policy is not None else catalog.JobSettings()
        self.openrouter = openrouter if openrouter is not None else OpenRouterSettings()

    def require_pool_enabled(self, pool):
        if pool == catalog.POOL:
            self.policy.require_enabled()
            return
        if pool == catalog.OPENROUTER_POOL:
            if not self.openrouter.enabled:
                raise JobError(503, "provider_unavailable")
            return
        raise JobError(409, "capability_unsupported")

    def _execution(self, draft):
        if draft.capability_id == catalog.CAPABILITY:
            if not self.policy.enabled:
                raise JobError(503, "jobs_disabled")
            return {"version": 1, "adapter": "test.image.v1", "connection_id": "test",
                    "model": "diagnostic", "resolution": f"{draft.width}x{draft.height}",
                    "output_format": "png", "allow_fallbacks": False,
                    "price_credits": catalog.PRICE}
        if draft.capability_id == catalog.OPENROUTER_CAPABILITY:
            try:
                return self.openrouter.execution_snapshot(draft.width, draft.height)
            except ValueError:
                raise JobError(409, "provider_unavailable") from None
        raise JobError(409, "capability_unsupported")

    def _assess(self, conn, owner, draft, now, execution):
        plans = EntitlementService(clock=lambda: now)
        plan = plans.resolve(conn, owner)
        if not plan.configured or plan.policy is None:
            raise JobError(403, "plan_unconfigured")
        media_repo.expire_unwritten(conn, owner, now)
        used, held = media_repo.usage(conn, owner)
        active = conn.execute(sa.select(sa.func.count()).select_from(t.jobs).where(
            t.jobs.c.account_id == owner, t.jobs.c.status.in_(ACTIVE))).scalar_one()
        submissions = conn.execute(sa.select(sa.func.count()).select_from(t.jobs).where(
            t.jobs.c.account_id == owner, t.jobs.c.created_at > now - plan.policy.window_seconds)).scalar_one()
        demand = ImageDemand(capability_id=draft.capability_id, executor="api",
            size=ImageSize(width=draft.width, height=draft.height), input_count=0,
            largest_input_bytes=0, output_bytes_bound=catalog.output_bound(draft.width, draft.height),
            reserve_credits=execution["price_credits"])
        usage = UsageSnapshot(account_id=owner, as_of=plan.as_of,
            window_seconds=plan.policy.window_seconds, active_jobs=active, submissions=submissions,
            committed_bytes=used, reserved_bytes=held)
        balance = CreditService(clock=lambda: now).overview(conn, owner, limit=1).balance
        feature_enabled = self.policy.enabled if draft.capability_id == catalog.CAPABILITY else self.openrouter.enabled
        decision = evaluate(plan, demand, RuntimeState(feature_enabled=feature_enabled,
            capability_supported=True, provider_available=True), usage, balance.available)
        if not decision.allowed:
            raise JobError(409, decision.code)
        return plan

    def quote(self, raw, csrf, draft: QuoteInput):
        draft = QuoteInput.model_validate(draft)
        execution = self._execution(draft)
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True, write=True)
            self._assess(conn, p.account_id, draft, p.now, execution)
            recent = conn.execute(sa.select(sa.func.count()).select_from(t.quotes).where(
                t.quotes.c.account_id == p.account_id, t.quotes.c.created_at > p.now - 3600)).scalar_one()
            if recent >= 100:
                raise JobError(429, "quote_rate_limited")
            quote_id = uuid4()
            version = catalog.VERSION if draft.capability_id == catalog.CAPABILITY else "openrouter-images-1"
            conn.execute(sa.insert(t.quotes).values(id=quote_id, account_id=p.account_id,
                request_json=draft.model_dump_json(), catalog_version=version,
                credits=execution["price_credits"], execution_json=json.dumps(execution, sort_keys=True),
                created_at=p.now, expires_at=p.now + 120))
            return QuoteView(id=quote_id, **draft.model_dump(), credits=execution["price_credits"],
                expires_at=p.now + 120, test_only=draft.capability_id == catalog.CAPABILITY,
                notice=("Тестовый исполнитель, не AI-модель. Расходуются тестовые баллы."
                        if draft.capability_id == catalog.CAPABILITY
                        else "Внешняя AI-модель OpenRouter; после подтверждения запрос может расходовать средства провайдера."))

    def submit(self, raw, csrf, command: CreateJob):
        command = CreateJob.model_validate(command)
        with self.auth.engine.begin() as conn:
            # A replay is a read of an existing receipt, not another admission.
            p = access.context(self.auth, conn, raw, csrf, mutation=True)
            old = conn.execute(sa.select(t.jobs).where(t.jobs.c.account_id == p.account_id,
                t.jobs.c.operation_id == command.operation_id)).mappings().first()
            if old is not None:
                if old["quote_id"] != command.quote_id:
                    raise JobError(409, "idempotency_conflict")
                return repo.view(old)
            quote = conn.execute(sa.select(t.quotes).where(t.quotes.c.id == command.quote_id,
                t.quotes.c.account_id == p.account_id)).mappings().first()
            if quote is None:
                raise JobError(404, "not_found")
            if quote["expires_at"] <= p.now:
                raise JobError(409, "quote_expired")
            if conn.execute(sa.select(t.jobs.c.id).where(t.jobs.c.quote_id == quote["id"])).first():
                raise JobError(409, "quote_already_used")
            draft = QuoteInput.model_validate_json(quote["request_json"])
            execution = json.loads(quote["execution_json"]) if quote["execution_json"] else self._execution(draft)
            current = self._execution(draft)
            if execution != current or quote["credits"] != execution["price_credits"]:
                raise JobError(409, "quote_expired")
            plan = self._assess(conn, p.account_id, draft, p.now, execution)
            job_id, output_id, reservation_id = uuid4(), uuid4(), uuid4()
            outputs.reserve(conn, p.account_id, output_id,
                catalog.output_bound(draft.width, draft.height), draft.width, draft.height, p.now)
            CreditService(clock=lambda: p.now).reserve(conn, p.account_id, Reserve(
                operation_id=uuid5(job_id, "reserve"), reservation_id=reservation_id,
                request_id=job_id, amount=quote["credits"]))
            conn.execute(sa.insert(t.jobs).values(id=job_id, account_id=p.account_id,
                operation_id=command.operation_id, quote_id=quote["id"], request_json=quote["request_json"],
                plan_snapshot=plan.model_dump_json(), execution_json=json.dumps(execution, sort_keys=True),
                pool=(catalog.POOL if draft.capability_id == catalog.CAPABILITY else catalog.OPENROUTER_POOL), status="queued",
                reservation_id=reservation_id, output_id=output_id, reserve_credits=quote["credits"],
                charged_credits=0, fence=0, next_poll_at=p.now, reconcile_count=0,
                cancel_requested=False, created_at=p.now, updated_at=p.now,
                deadline_at=p.now + self.policy.deadline_seconds))
            repo.event(conn, job_id, "queued", p.now)
            return repo.view(repo.load(conn, p.account_id, job_id))

    def get(self, raw, job_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw)
            return repo.view(repo.load(conn, p.account_id, job_id))

    def list(self, raw, limit=20, offset=0):
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 10000:
            raise JobError(422, "invalid_pagination")
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw)
            rows = conn.execute(sa.select(t.jobs).where(t.jobs.c.account_id == p.account_id)
                .order_by(t.jobs.c.created_at.desc(), t.jobs.c.id.desc())
                .limit(limit + 1).offset(offset)).mappings().all()
            return JobList(jobs=[repo.view(row) for row in rows[:limit]],
                           next_offset=offset + limit if len(rows) > limit else None)

    def release_terminal(self, conn, row, state, code=None):
        """Only before any external write. Caller holds Account and Job locks."""
        if state not in {"failed", "cancelled"} or row["status"] in TERMINAL:
            raise JobError(409, "invalid_transition")
        now = self.auth.now()
        outputs.release(conn, row["account_id"], row["output_id"])
        CreditService(clock=lambda: now).release(conn, row["account_id"], Release(
            operation_id=uuid5(row["id"], "release"), reservation_id=row["reservation_id"]))
        repo.close_attempt(conn, row, state, now)
        repo.change(conn, row["id"], now, status=state, error_code=code, lease_until=None)
        repo.event(conn, row["id"], state, now)

    def cancel(self, raw, csrf, job_id):
        with self.auth.engine.begin() as conn:
            p = access.context(self.auth, conn, raw, csrf, mutation=True)
            row = repo.load(conn, p.account_id, job_id)
            if row["status"] in TERMINAL:
                return repo.view(row)
            if not row["cancel_requested"]:
                repo.change(conn, job_id, p.now, cancel_requested=True)
                repo.event(conn, job_id, "cancel_requested", p.now)
            if row["status"] in {"queued", "claimed", "running"}:
                self.release_terminal(conn, row, "cancelled")
            # Once sealed, an S3 write may exist. Do NOT free space or credits;
            # accepted completion/reconciliation owns the final outcome.
            return repo.view(repo.load(conn, p.account_id, job_id))

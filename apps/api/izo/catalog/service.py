"""Finite approved model registry with staff CAS and immutable price metadata."""
import sqlalchemy as sa
from uuid import uuid4

from ..accounts.admin_access import session_owner, staff_session
from ..accounts.security import AuthError
from ..admin import tables as admin_tables
from . import tables as t
from .schemas import APPROVED, PRICE_COLUMNS, PROVIDERS, CatalogPatch, CatalogView, ModelView, Price


APPROVED_BY_ID = {item[0]: item for item in APPROVED}
CATALOG_PERMISSIONS = frozenset(("catalog.read", "catalog.write", "pricing.write"))


class CatalogError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(code)


class CatalogService:
    def __init__(self, auth):
        self.auth = auth
        self.engine = auth.engine

    def snapshot(self, conn, *, lock=True):
        if not t.ensure_test_seed(conn, self.auth.now()):
            raise CatalogError(503, "catalog_unavailable")
        statement = sa.select(t.state).where(t.state.c.id == 1)
        if lock:
            statement = statement.with_for_update(read=True)
        head = conn.execute(statement).mappings().one()
        rows = conn.execute(sa.select(t.models)).mappings().all()
        by_id = {row["id"]: row for row in rows}
        if set(by_id) != set(APPROVED_BY_ID):
            raise CatalogError(503, "catalog_unavailable")
        models = []
        for model_id, provider, modality, label in APPROVED:
            row = by_id[model_id]
            if (row["provider"], row["modality"], row["label"]) != (provider, modality, label):
                raise CatalogError(503, "catalog_unavailable")
            models.append(ModelView(id=model_id, provider=provider, modality=modality,
                label=label, published=row["published"], enabled=row["enabled"],
                is_default=model_id == head["default_model"],
                publishable=modality == "text", price=Price.from_row(row),
                price_source=("admin_manual" if any(row[name] is not None
                    for name in PRICE_COLUMNS) else "unset"), updated_at=row["updated_at"]))
        if not any(m.is_default and m.published and m.enabled and m.modality == "text"
                   for m in models):
            raise CatalogError(503, "catalog_unavailable")
        return head, models

    def _view(self, conn, grants) -> CatalogView:
        head, models = self.snapshot(conn)
        return CatalogView(revision=head["revision"],
            permissions=sorted(set(grants) & CATALOG_PERMISSIONS),
            providers=list(PROVIDERS), models=models)

    def read(self, raw) -> CatalogView:
        with self.engine.begin() as conn:
            _, _, grants = staff_session(self.auth, conn, raw, {"catalog.read"})
            return self._view(conn, grants)

    def public_text(self, conn, *, lock=True):
        head, models = self.snapshot(conn, lock=lock)
        return head, [m for m in models if m.modality == "text" and m.published and m.enabled]

    def patch(self, raw, csrf, model_id: str, command: CatalogPatch) -> CatalogView:
        try:
            return self._patch(raw, csrf, model_id, command)
        except (AuthError, CatalogError) as error:
            if error.status != 401:
                self._audit_denied(raw, model_id)
            raise

    def _audit_denied(self, raw, model_id):
        with self.engine.begin() as conn:
            try:
                actor = session_owner(conn, raw)
            except AuthError:
                return
            conn.execute(sa.insert(admin_tables.events).values(
                id=uuid4(), actor_id=actor, action="catalog.update", outcome="denied",
                case_reference=model_id if model_id in APPROVED_BY_ID else None,
                created_at=self.auth.now()))

    def _patch(self, raw, csrf, model_id: str, command: CatalogPatch) -> CatalogView:
        command = CatalogPatch.model_validate(command.model_dump())
        fingerprint = command.fingerprint(model_id)
        with self.engine.begin() as conn:
            actor, _, grants = staff_session(self.auth, conn, raw,
                {"catalog.read", "catalog.write"}, csrf=csrf, mutation=True)
            if model_id not in APPROVED_BY_ID:
                raise CatalogError(422, "model_not_allowed")
            if command.operation_id.int == 0:
                raise CatalogError(422, "invalid_operation")
            if command.enabled and not command.published:
                raise CatalogError(422, "enabled_requires_publication")
            modality = APPROVED_BY_ID[model_id][2]
            if modality == "image":
                if command.published or command.enabled or command.is_default:
                    raise CatalogError(409, "image_runtime_not_bound")
                if (command.price.input_kopeks_per_million is not None
                        or command.price.output_kopeks_per_million is not None):
                    raise CatalogError(422, "invalid_price_shape")
            elif command.price.image_kopeks_per_image is not None:
                raise CatalogError(422, "invalid_price_shape")
            if command.is_default and (not command.published or not command.enabled):
                raise CatalogError(422, "default_not_enabled")
            if not t.ensure_test_seed(conn, self.auth.now()):
                raise CatalogError(503, "catalog_unavailable")
            head = conn.execute(sa.select(t.state).where(t.state.c.id == 1)
                                .with_for_update()).mappings().one()
            old = conn.execute(sa.select(t.events).where(
                t.events.c.operation_id == command.operation_id)).mappings().first()
            if old:
                if old["actor_id"] != actor["id"] or old["fingerprint"] != fingerprint:
                    raise CatalogError(409, "catalog_operation_conflict")
                return self._view(conn, grants)
            if head["revision"] != command.expected_revision:
                raise CatalogError(409, "catalog_revision_conflict")
            row = conn.execute(sa.select(t.models).where(t.models.c.id == model_id)
                               .with_for_update()).mappings().one()
            price = command.price.model_dump(exclude={"currency"})
            if any(row[name] != price[name] for name in PRICE_COLUMNS) and "pricing.write" not in grants:
                raise AuthError(403, "forbidden")
            if head["default_model"] == model_id and not command.is_default:
                raise CatalogError(409, "default_required")
            next_default = model_id if command.is_default else head["default_model"]
            new_revision = head["revision"] + 1
            updated = conn.execute(sa.update(t.state).where(t.state.c.id == 1,
                t.state.c.revision == command.expected_revision).values(
                revision=new_revision, default_model=next_default,
                updated_at=self.auth.now()))
            if updated.rowcount != 1:
                raise CatalogError(409, "catalog_revision_conflict")
            before = dict(published=row["published"], enabled=row["enabled"],
                          is_default=head["default_model"] == model_id,
                          default_model=head["default_model"],
                          price=Price.from_row(row).model_dump())
            after = dict(published=command.published, enabled=command.enabled,
                         is_default=command.is_default, default_model=next_default,
                         price=command.price.model_dump())
            conn.execute(sa.update(t.models).where(t.models.c.id == model_id).values(
                published=command.published, enabled=command.enabled,
                updated_at=self.auth.now(), **price))
            conn.execute(sa.insert(t.events).values(
                operation_id=command.operation_id, actor_id=actor["id"],
                model_id=model_id, revision=new_revision, fingerprint=fingerprint,
                reason=command.reason.strip(), before_json=before, after_json=after,
                created_at=self.auth.now()))
            return self._view(conn, grants)

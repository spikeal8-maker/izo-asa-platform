"""Read-only runtime catalog resolver used by job admission.

CATALOG-001 cannot activate paid connections: migration allows only disabled.
The resolver nevertheless validates the full published/proof/binding chain so a
later activation package has one fail-closed boundary instead of shared env.
"""
import sqlalchemy as sa

from . import repository as repo, tables as t
from .schemas import CapabilityContent, CatalogError, ConnectionContent

ADAPTER = "openrouter.images.v1"


def resolve_execution(conn, capability_id: str, width: int, height: int) -> dict:
    if capability_id != "openrouter.image.v1":
        raise CatalogError(409, "capability_unsupported")
    cap_head = repo.head(conn, t.capability_heads, t.capability_heads.c.capability_id, capability_id)
    if not cap_head or not cap_head["published_revision_id"]:
        raise CatalogError(503, "provider_unavailable")
    cap = repo.revision(conn, t.capability_revisions, cap_head["published_revision_id"])
    content = CapabilityContent.model_validate_json(cap["content_json"])
    connection_head = repo.head(conn, t.connection_heads, t.connection_heads.c.connection_id,
                            content.connection_id)
    if (not connection_head or not connection_head["published_revision_id"]
            or connection_head["runtime_state"] != "active"):
        raise CatalogError(503, "provider_unavailable")
    connection = repo.revision(conn, t.connection_revisions,
                               connection_head["published_revision_id"])
    connection_content = ConnectionContent.model_validate_json(connection["content_json"])
    credential = repo.active_credential(conn, content.connection_id)
    proof = conn.execute(sa.select(t.proofs).where(
        t.proofs.c.capability_id == capability_id,
        t.proofs.c.connection_id == content.connection_id,
        t.proofs.c.capability_hash == cap["content_hash"],
        t.proofs.c.connection_hash == connection["content_hash"],
        t.proofs.c.credential_version == (credential["version"] if credential else -1),
    ).order_by(t.proofs.c.created_at.desc()).limit(1)).mappings().first()
    if not credential or not proof:
        raise CatalogError(503, "provider_unavailable")
    pixels = {"512": 512, "1K": 1024, "2K": 2048, "4K": 4096}
    resolution = next((item for item in content.resolutions
                       if width == height == pixels[item]), None)
    if resolution is None or content.price_credits <= 0 or connection_content.spend_cap_minor <= 0:
        raise CatalogError(409, "provider_unavailable")
    return {
        "version": 1, "adapter": ADAPTER, "connection_id": content.connection_id,
        "model": content.model_id, "resolution": resolution, "output_format": "png",
        "allow_fallbacks": connection_content.allow_fallbacks,
        "price_credits": content.price_credits,
    }

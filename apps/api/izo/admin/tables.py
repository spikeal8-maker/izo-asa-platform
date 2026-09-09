"""Admin cap and append-only safe events, not another ledger or identity system."""
import sqlalchemy as sa
from ..accounts.admin_access import metadata

policies = sa.Table("admin_grant_policies", metadata,
    sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), primary_key=True),
    sa.Column("max_grant", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("max_grant >= 0 AND max_grant <= 1000000000", name="admin_grant_bound"))
events = sa.Table("admin_events", metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("actor_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False, index=True),
    sa.Column("target_id", sa.Uuid),
    sa.Column("action", sa.String(48), nullable=False),
    sa.Column("outcome", sa.String(8), nullable=False),
    sa.Column("case_reference", sa.String(64)),
    sa.Column("operation_id", sa.Uuid, unique=True),
    sa.Column("entry_id", sa.Uuid),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("outcome IN ('success','denied')", name="admin_event_outcome"))

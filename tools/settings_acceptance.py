"""Isolated PostgreSQL/HTTP acceptance for SETTINGS-002 after Entitlements fixture setup."""
import json
import os
import sys
from uuid import UUID, uuid4

import sqlalchemy as sa

from izo.config import Settings
from izo.accounts.repository import create_auth_engine
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.accounts import tables as account_tables
from izo.access.service import AccessService
from izo.access import tables as access_tables
from izo.access.permissions import GLOBAL_DELEGABLE
from izo.entitlements.service import EntitlementService
from izo.entitlements.schemas import SetDefault
from auth_acceptance import Client, check
from admin_acceptance import call, create_fixture


def access_grant(permission, password):
    return {"operation_id":str(uuid4()), "permission":permission, "scope":"global",
            "ttl_seconds":7200, "case_reference":"SETTINGS-"+uuid4().hex,
            "current_password":password}


def publish_payload(version, policy, operation=None):
    return {"operation_id":str(operation or uuid4()), "expected_revision":version,
            "policy":policy, "reason":"SETTINGS-002 isolated acceptance"}


def cleanup_bootstrap_owner(auth, owner_id):
    with auth.engine.begin() as conn:
        conn.execute(sa.delete(access_tables.ceilings).where(access_tables.ceilings.c.account_id==owner_id))
        conn.execute(sa.delete(access_tables.grants).where(access_tables.grants.c.account_id==owner_id))
        conn.execute(sa.delete(account_tables.permissions).where(
            account_tables.permissions.c.account_id==owner_id,
            account_tables.permissions.c.permission.in_(GLOBAL_DELEGABLE)))
        conn.execute(sa.update(access_tables.state).where(access_tables.state.c.id==1)
                     .values(version=access_tables.state.c.version+1))
        grants=conn.execute(sa.select(sa.func.count()).select_from(access_tables.grants).where(
            access_tables.grants.c.account_id==owner_id)).scalar_one()
        ceilings=conn.execute(sa.select(sa.func.count()).select_from(access_tables.ceilings).where(
            access_tables.ceilings.c.account_id==owner_id)).scalar_one()
        materialized=conn.execute(sa.select(sa.func.count()).select_from(account_tables.permissions).where(
            account_tables.permissions.c.account_id==owner_id,
            account_tables.permissions.c.permission.in_(GLOBAL_DELEGABLE))).scalar_one()
        check(grants==ceilings==materialized==0,"settings_bootstrap_owner_cleanup")


def before(auth):
    owner_client,owner=create_fixture(auth,"Synthetic Settings Access Owner")
    operator_client,operator=create_fixture(auth,"Synthetic Settings Operator")
    AccessService(auth).enroll_local_owner(UUID(owner["id"]))
    for permission in ("plans.read","plans.write"):
        status,_=call(owner_client,"POST","admin/access/subjects/"+operator["id"]+"/grants",
                      access_grant(permission,owner["password"]))
        check(status==200,"settings_access_"+permission.replace('.','_'))
    status,current=call(operator_client,"GET","admin/settings/basic")
    check(status==200 and current["revision"] is not None,"settings_requires_existing_basic")
    original_policy=current["policy"]
    original_revision=current["revision"]
    original_revision_id=current["revision_id"]
    original_hash=current["policy_hash"]
    version=current["default_version"]
    candidate=dict(original_policy)
    active=int(candidate["active_jobs"])
    candidate["active_jobs"]=active-1 if active>1 else active+1
    preview={"expected_revision":version,"policy":candidate}
    status,view=call(operator_client,"POST","admin/settings/basic/preview",preview)
    check(status==200 and view["generation_enabled"] and
          any(item["key"]=="plan.active_jobs" for item in view["diff"]),"settings_preview")
    operation=uuid4(); payload=publish_payload(version,candidate,operation)
    status,published=call(operator_client,"POST","admin/settings/basic/publish",payload)
    check(status==200 and published["default_version"]==version+1,"settings_publish")
    check(call(operator_client,"POST","admin/settings/basic/publish",payload)==(status,published),
          "settings_publish_exact_replay")
    changed={**payload,"policy":{**candidate,"active_jobs":candidate["active_jobs"]+1}}
    check(call(operator_client,"POST","admin/settings/basic/publish",changed)[0]==409,
          "settings_publish_idempotency_conflict")
    rollback={"operation_id":str(uuid4()),"expected_revision":version+1,
              "target_revision":original_revision,"reason":"restore pre-settings policy"}
    status,rolled=call(operator_client,"POST","admin/settings/basic/rollback",rollback)
    check(status==200 and rolled["default_version"]==version+2,"settings_rollback")
    status,restored=call(operator_client,"GET","admin/settings/basic")
    check(status==200 and restored["policy"]==original_policy and
          restored["policy_hash"]==original_hash,"settings_restore_values")
    history=call(operator_client,"GET","admin/settings/basic/history?limit=5")
    check(history[0]==200 and any(item["revision"]==rolled["revision"]
          and item["active"] for item in history[1]["items"]),"settings_history")
    with auth.engine.begin() as conn:
        EntitlementService().set_default(conn,UUID(operator["id"]),SetDefault(
            operation_id=uuid4(),revision_id=UUID(original_revision_id),expected_version=version+2,
            reason="restore exact pre-settings default for shared acceptance"))
    status,cleaned=call(operator_client,"GET","admin/settings/basic")
    check(status==200 and cleaned["revision_id"]==original_revision_id and
          cleaned["policy_hash"]==original_hash,"settings_exact_default_restored")
    cleanup_bootstrap_owner(auth,UUID(owner["id"]))
    print("SETTINGS_BEFORE_OK: ACCESS provisioning, preview, publish/replay/conflict and rollback",file=sys.stderr)
    return {"operator":operator,"rollback":rollback,"receipt":rolled,
            "policy_hash":original_hash,"revision_id":original_revision_id,
            "default_version":version+3}


def after(auth,state):
    operator=state["operator"]
    client=Client(auth.policy.cookie_name,operator["raw"]); client.csrf=operator["csrf"]
    status,current=call(client,"GET","admin/settings/basic")
    check(status==200 and current["policy_hash"]==state["policy_hash"] and
          current["revision_id"]==state["revision_id"] and
          current["default_version"]==state["default_version"],"settings_persisted")
    replay=call(client,"POST","admin/settings/basic/rollback",state["rollback"])
    check(replay[0]==200 and replay[1]==state["receipt"],"settings_rollback_replay_after_restart")
    status,current=call(client,"GET","admin/settings/basic")
    check(status==200 and current["revision_id"]==state["revision_id"] and
          current["default_version"]==state["default_version"],"settings_replay_did_not_rewrite_default")
    print("SETTINGS_AFTER_OK: policy values, ACCESS permissions and rollback receipt survived restart",
          file=sys.stderr)


def main():
    if os.getenv("IZO_ENVIRONMENT")!="test" or os.getenv("IZO_SETTINGS_ACCEPTANCE")!="isolated":
        raise SystemExit("Disposable isolated test stack only")
    auth=AuthService(create_auth_engine(Settings()),AuthSettings())
    try:
        if sys.argv[1:]==["before"]:
            json.dump(before(auth),sys.stdout)
        elif sys.argv[1:]==["after"]:
            after(auth,json.load(sys.stdin))
        else:
            raise SystemExit("Expected before or after")
    finally:
        auth.engine.dispose()


if __name__=="__main__":
    main()

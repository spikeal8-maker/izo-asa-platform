"""Opted-in PostgreSQL/HTTP acceptance for ACCESS-001 before and after restart."""
import json
import os
import sys
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from izo.config import Settings
from izo.accounts.repository import create_auth_engine
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.access.service import AccessService
from izo.access import tables as access_tables
from izo.accounts import tables as accounts
from auth_acceptance import Client, check
from admin_acceptance import call, create_fixture


def auth_service():
    config=Settings()
    return AuthService(create_auth_engine(config), AuthSettings())


def grant_payload(permission, password, operation=None, case=None, ttl=3600):
    return {"operation_id":str(operation or uuid4()), "permission":permission,
            "scope":"global", "ttl_seconds":ttl,
            "case_reference":case or "ACCESS-PG-"+uuid4().hex,
            "current_password":password}


def revoke_payload(permission, password, operation=None, case=None):
    return {"operation_id":str(operation or uuid4()), "permission":permission,
            "scope":"global", "case_reference":case or "ACCESS-PG-"+uuid4().hex,
            "current_password":password}


def before(auth):
    owner_client,owner=create_fixture(auth,"Synthetic Access Owner")
    target_client,target=create_fixture(auth,"Synthetic Access Target")
    service=AccessService(auth)
    service.enroll_local_owner(UUID(owner["id"]))
    me=call(owner_client,"GET","admin/access/me")
    check(me[0]==200 and "plans.write" in me[1]["delegation_ceiling"],"owner_ceiling")
    check(call(target_client,"GET","admin/access/me")[0]==403,"delegate_without_access_denied")

    read_grant=grant_payload("access.read",owner["password"],case="ACCESS-READ-"+uuid4().hex,ttl=7200)
    manage_grant=grant_payload("access.manage",owner["password"],case="ACCESS-MANAGE-"+uuid4().hex)
    check(call(owner_client,"POST","admin/access/subjects/"+target["id"]+"/grants",read_grant)[0]==200,"access_read_grant")
    check(call(owner_client,"POST","admin/access/subjects/"+target["id"]+"/grants",manage_grant)[0]==200,"access_manage_grant")
    with auth.engine.begin() as conn:
        conn.execute(sa.insert(access_tables.ceilings).values(account_id=UUID(target["id"]),
            permission="access.manage",scope="global",granted_by=None,created_at=auth.now(),expires_at=auth.now()+3600))
    denied=call(target_client,"POST","admin/access/subjects/"+owner["id"]+"/revocations",
                revoke_payload("access.manage",target["password"],case="ACCESS-LAST-"+uuid4().hex))
    check(denied[0]==409 and denied[1]["error"]["code"]=="last_access_owner","finite_owner_not_last_owner")

    second_client,second=create_fixture(auth,"Synthetic Access Owner Two")
    service.enroll_local_owner(UUID(second["id"]))
    operation=uuid4(); case="ACCESS-PG-"+uuid4().hex
    payload=grant_payload("plans.write",second["password"],operation,case)
    first=call(second_client,"POST","admin/access/subjects/"+target["id"]+"/grants",payload)
    replay=call(second_client,"POST","admin/access/subjects/"+target["id"]+"/grants",payload)
    check(first[0]==200 and replay==first,"grant_exact_replay")
    status,view=target_client.call("GET","/me")
    check(status==200 and "plans.write" in view["account"]["permissions"],"materialized_permission")
    revoke_op=uuid4(); revoke_case="ACCESS-PG-"+uuid4().hex
    revoke=revoke_payload("plans.write",second["password"],revoke_op,revoke_case)
    r1=call(second_client,"POST","admin/access/subjects/"+target["id"]+"/revocations",revoke)
    r2=call(second_client,"POST","admin/access/subjects/"+target["id"]+"/revocations",revoke)
    check(r1[0]==200 and r2==r1,"revoke_exact_replay")
    persistent=grant_payload("catalog.read",second["password"],case="ACCESS-PERSIST-"+uuid4().hex)
    check(call(second_client,"POST","admin/access/subjects/"+target["id"]+"/grants",persistent)[0]==200,"persistent_grant")

    with auth.engine.begin() as conn:
        version=conn.execute(sa.select(access_tables.state.c.version)).scalar_one()
        check(version>=7,"access_state_version")
        for statement in ["UPDATE staff_access_operations SET action='grant'",
                          "DELETE FROM staff_access_operations",
                          "TRUNCATE staff_access_operations"]:
            refused=False
            try:
                with conn.begin_nested(): conn.exec_driver_sql(statement)
            except DBAPIError: refused=True
            check(refused,"immutable_access_receipts")
    print("ACCESS_BEFORE_OK: replay, materialization, immutable receipts and permanent-owner guard",file=sys.stderr)
    return {"owner":owner,"target":target,"second":second,"persistent":persistent}


def after(auth,state):
    owner=state["owner"]; target=state["target"]
    owner_client=Client(auth.policy.cookie_name,owner["raw"]); owner_client.csrf=owner["csrf"]
    target_client=Client(auth.policy.cookie_name,target["raw"]); target_client.csrf=target["csrf"]
    status,subject=call(owner_client,"GET","admin/access/subjects/"+target["id"])
    check(status==200 and any(p["permission"]=="catalog.read" and p["managed"]
                              for p in subject["permissions"]),"access_persisted")
    status,view=target_client.call("GET","/me")
    check(status==200 and "catalog.read" in view["account"]["permissions"],"materialized_persisted")
    revoke=revoke_payload("catalog.read",owner["password"],case="ACCESS-AFTER-"+uuid4().hex)
    check(call(owner_client,"POST","admin/access/subjects/"+target["id"]+"/revocations",revoke)[0]==200,
          "post_restart_revoke")
    status,view=target_client.call("GET","/me")
    check(status==200 and "catalog.read" not in view["account"]["permissions"],"revoke_effective")
    second=state["second"]
    second_client=Client(auth.policy.cookie_name,second["raw"]); second_client.csrf=second["csrf"]
    rotated=call(owner_client,"POST","admin/access/subjects/"+second["id"]+"/revocations",
                 revoke_payload("access.manage",owner["password"],case="ACCESS-ROTATE-"+uuid4().hex))
    check(rotated[0]==200,"permanent_owner_rotation")
    denied=call(second_client,"POST","admin/access/subjects/"+target["id"]+"/grants",
                grant_payload("plans.read",second["password"],case="ACCESS-OLD-OWNER-"+uuid4().hex))
    check(denied[0]==403,"revoked_owner_cannot_manage")
    check(call(owner_client,"GET","admin/access/me")[0]==200,"remaining_owner_active")
    print("ACCESS_AFTER_OK: provenance, restart and permanent-owner rotation verified",file=sys.stderr)


def main():
    if os.getenv("IZO_ACCESS_ACCEPTANCE") != "isolated":
        raise SystemExit("ACCESS acceptance requires explicit isolated opt-in")
    if len(sys.argv)!=2 or sys.argv[1] not in {"before","after"}:
        raise SystemExit("usage: access_acceptance.py before|after")
    auth=auth_service()
    try:
        if sys.argv[1]=="before":
            json.dump(before(auth),sys.stdout)
        else:
            after(auth,json.load(sys.stdin))
    finally:
        auth.engine.dispose()


if __name__ == "__main__":
    main()

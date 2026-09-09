"""Opted-in disposable PostgreSQL + HTTP fixtures; secrets only in RUNNER_TEMP.

before prepares distinct recipients for HTTP races and a real-browser grant.
after checks both after actual Compose down/up. Immutable audit is NOT disabled
for cleanup: disposable CI volumes are removed by the existing finalizer.
"""
import json
import os
import secrets
import sys
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from izo.config import Settings
from izo.accounts import tables as a, repository as ar
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.admin.service import AdminService
from izo.admin import tables as t
from izo.credits import tables as c
from auth_acceptance import Client, check


def call(client, method, path, data=None):
    headers={"Cookie":client.name+"="+client.raw,"Origin":"http://localhost:8080",
             "Content-Type":"application/json","X-IZO-Request":"web","X-CSRF-Token":client.csrf}
    req=Request("http://api:8000/api/v1/"+path, headers=headers, method=method,
                data=json.dumps(data).encode() if data is not None else None)
    try:
        response=urlopen(req,timeout=20)
    except HTTPError as error:
        response=error
    with response:
        body=response.read(131072)
        return response.status,json.loads(body) if body else None


def create_fixture(auth, name):
    email="admin-ci-"+uuid4().hex+"@example.invalid"
    password=secrets.token_urlsafe(24)
    client=Client(auth.policy.cookie_name)
    status,body=client.call("POST","/register", {"email":email,"password":password,
        "display_name":name,"invite_code":auth.issue_invite()})
    check(status==201,"fixture_registration")
    uid=UUID(body["account"]["id"])
    with auth.engine.begin() as conn:
        conn.execute(sa.update(a.identities).where(a.identities.c.account_id==uid).values(verified_at=auth.now()))
    return client,{"id":str(uid),"public_code":body["account"]["public_code"],
                   "email":email,"password":password,"raw":client.raw,"csrf":client.csrf}


def before(auth):
    staff,operator=create_fixture(auth,"Synthetic Operator")
    user,recipient=create_fixture(auth,"Synthetic HTTP Recipient")
    browser_staff,live_operator=create_fixture(auth,"Synthetic Browser Operator")
    browser_user,live_recipient=create_fixture(auth,"Synthetic Browser Recipient")
    readonly,limited=create_fixture(auth,"Synthetic Read Only")
    service=AdminService(auth)
    service.enroll_local_operator(UUID(operator["id"]),1000)
    service.enroll_local_operator(UUID(live_operator["id"]),1000)
    with auth.engine.begin() as conn:
        conn.execute(sa.insert(a.permissions).values(account_id=UUID(limited["id"]),permission="users.read_limited"))
    path="admin/users/"+recipient["id"]+"/compensations"
    payload={"operation_id":str(uuid4()),"case_reference":"PG-"+uuid4().hex,
             "amount":30,"current_password":operator["password"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:call(staff,"POST",path,payload),range(2)))
    check(all(status==200 for status,_ in results) and results[0][1]==results[1][1],"grant_race_replay")
    check(call(staff,"POST",path,{**payload,"operation_id":str(uuid4())})[0]==409,"duplicate_case")
    check(call(readonly,"GET","admin/users/"+recipient["id"])[0]==200,"readonly_metadata")
    check(call(readonly,"GET","admin/users/"+recipient["id"]+"/credits")[0]==403,"readonly_balance_denied")
    check(call(user,"GET","admin/audit")[0]==403,"ordinary_admin_denied")
    check(call(user,"GET","credits")[1]["balance"]["available"]==30,"owner_sees_grant")
    for statement in ["UPDATE admin_events SET action='changed'", "DELETE FROM admin_events", "TRUNCATE admin_events"]:
        with auth.engine.begin() as conn:
            refused=False
            try:
                with conn.begin_nested(): conn.exec_driver_sql(statement)
            except DBAPIError: refused=True
            check(refused,"immutable_admin_audit")
    # Two administrators targeting each other: consistent account locks, no deadlock.
    commands=[(staff,live_operator["id"],operator["password"]),(browser_staff,operator["id"],live_operator["password"])]
    def cross(item):
        client,target,password=item
        return call(client,"POST","admin/users/"+target+"/compensations",{
            "operation_id":str(uuid4()),"case_reference":"CROSS-"+uuid4().hex,"amount":1,"current_password":password})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        check(list(pool.map(cross,commands))==[200,200],"cross_staff_no_deadlock")
    print("ADMIN_BEFORE_OK: authorized HTTP grant/replay, PG races, scope isolation and immutable audit",file=sys.stderr)
    return {"operator":operator,"recipient":recipient,"live_operator":live_operator,
            "live_recipient":live_recipient,"payload":payload,"live_case":"LIVE-"+uuid4().hex}


def after(auth,state):
    operator=state["operator"]
    client=Client(auth.policy.cookie_name,operator["raw"]);client.csrf=operator["csrf"]
    recipient=state["recipient"]["id"]
    check(call(client,"GET","admin/users/"+recipient+"/credits")[1]["balance"]["available"]==30,"grant_persisted")
    check(call(client,"POST","admin/users/"+recipient+"/compensations",state["payload"])[0]==200,"replay_after_restart")
    with auth.engine.begin() as conn:
        live_id=UUID(state["live_recipient"]["id"])
        entries=conn.execute(sa.select(c.ledger).where(c.ledger.c.account_id==live_id)).mappings().all()
        check(len(entries)==1 and entries[0]["balance_delta"]==40,"real_browser_one_grant_persisted")
        check(conn.execute(sa.select(sa.func.count()).select_from(t.events).where(
            t.events.c.case_reference==state["live_case"].upper())).scalar_one()==1,"real_browser_audit_persisted")
        conn.execute(sa.delete(a.permissions).where(a.permissions.c.account_id==UUID(operator["id"])))
    check(call(client,"GET","admin/users/"+recipient)[0]==403,"revoked_permission_after_restart")
    print("ADMIN_AFTER_OK: HTTP/browser grants and immutable receipts persisted; replay unchanged; permission revoke effective",file=sys.stderr)


def main():
    if os.getenv("IZO_ENVIRONMENT")!="test" or os.getenv("IZO_ADMIN_ACCEPTANCE")!="isolated":
        raise SystemExit("Disposable isolated test stack only")
    engine=ar.create_auth_engine(Settings())
    auth=AuthService(engine,AuthSettings())
    try:
        if sys.argv[1:]==["before"]:
            print(json.dumps(before(auth)))
        elif sys.argv[1:]==["after"]:
            after(auth,json.load(sys.stdin))
        else:
            raise SystemExit("Expected before or after")
    finally: engine.dispose()


if __name__=="__main__": main()

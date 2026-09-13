"""CATALOG-002 PostgreSQL/HTTP/race/restart acceptance. No provider network or raw secret."""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from auth_acceptance import Client, check
from admin_acceptance import call, create_fixture
from izo.accounts import tables as account_tables
from izo.accounts.repository import create_auth_engine
from izo.accounts.service import AuthService
from izo.accounts.settings import AuthSettings
from izo.access import tables as access_tables
from izo.access.permissions import GLOBAL_DELEGABLE
from izo.access.service import AccessService
from izo.catalog import tables as t
from izo.catalog.schemas import CapabilityDraft, ConnectionDraft, CredentialBind, ProofInput, PublishInput, RevokeCredential
from izo.catalog.service import CatalogService
from izo.config import Settings
from izo.jobs import catalog as job_catalog

PERMISSIONS=("catalog.read","catalog.write","connections.read","connections.write","secrets.bind")
CONNECTION="fal-klein-4b-v1"
CAPABILITY="fal.flux2.klein.4b"


def grant_payload(permission,password):
    return {"operation_id":str(uuid4()),"permission":permission,"scope":"global","ttl_seconds":7200,
            "case_reference":"CATALOG-"+uuid4().hex,"current_password":password}


def connection(operation=None,expected=0):
    return ConnectionDraft(operation_id=operation or uuid4(),expected_version=expected,
        reason="CATALOG-002 isolated acceptance",provider_id="fal",account_ref="fal-ci-account",
        project_ref="images",environment="test",max_concurrency=2,rate_limit=20,
        rate_window_seconds=60,timeout_seconds=180)


def capability(operation=None,expected=0,name="FLUX.2 Klein CI"):
    return CapabilityDraft(operation_id=operation or uuid4(),expected_version=expected,
        reason="CATALOG-002 isolated acceptance",name=name,help="offline catalog contract only",
        adapter_id="fal.images.v1",model_id="fal-ai/flux-2/klein/4b",connection_id=CONNECTION)


def credential(password,operation=None,expected=1,version=1):
    ref="IZO_FAL_KEY" if version==1 else "vault/izo/fal/ci-v2"
    source="env" if version==1 else "secret_manager"
    return CredentialBind(operation_id=operation or uuid4(),expected_version=expected,
        reason="CATALOG-002 credential metadata",source_type=source,secret_ref=ref,environment="test",
        account_ref="fal-ci-account",project_ref="images",current_password=password)


def cleanup_bootstrap_owner(auth,owner_id):
    with auth.engine.begin() as conn:
        conn.execute(sa.delete(access_tables.ceilings).where(access_tables.ceilings.c.account_id==owner_id))
        conn.execute(sa.delete(access_tables.grants).where(access_tables.grants.c.account_id==owner_id))
        conn.execute(sa.delete(account_tables.permissions).where(
            account_tables.permissions.c.account_id==owner_id,
            account_tables.permissions.c.permission.in_(GLOBAL_DELEGABLE)))
        conn.execute(sa.update(access_tables.state).where(access_tables.state.c.id==1)
                     .values(version=access_tables.state.c.version+1))
        check(conn.execute(sa.select(sa.func.count()).select_from(access_tables.grants).where(
            access_tables.grants.c.account_id==owner_id)).scalar_one()==0,"catalog_owner_grants_cleanup")
        check(conn.execute(sa.select(sa.func.count()).select_from(access_tables.ceilings).where(
            access_tables.ceilings.c.account_id==owner_id)).scalar_one()==0,"catalog_owner_ceiling_cleanup")


def immutable(engine):
    for sql in ("UPDATE catalog_capability_revisions SET revision=revision",
                "DELETE FROM catalog_connection_revisions",
                "UPDATE catalog_contract_proofs SET evidence_hash=evidence_hash",
                "DELETE FROM catalog_changes","TRUNCATE catalog_changes"):
        try:
            with engine.begin() as conn: conn.execute(sa.text(sql))
        except DBAPIError as exc:
            check(getattr(exc.orig,"sqlstate",None)=="55000","catalog_immutable_sqlstate")
        else:
            raise AssertionError("catalog_history_mutated")


def before(auth):
    owner_client,owner=create_fixture(auth,"Synthetic Catalog Access Owner")
    operator_client,operator=create_fixture(auth,"Synthetic Catalog Operator")
    ordinary,_=create_fixture(auth,"Synthetic Catalog Ordinary")
    AccessService(auth).enroll_local_owner(UUID(owner["id"]))
    for permission in PERMISSIONS:
        status,_=call(owner_client,"POST","admin/access/subjects/"+operator["id"]+"/grants",
                      grant_payload(permission,owner["password"]))
        check(status==200,"catalog_access_"+permission.replace('.','_'))

    race_id="fal.race.metadata"
    race_commands=[capability(name="Initial Race A"),capability(name="Initial Race B")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        race_results=list(pool.map(lambda pair:call(pair[0],"POST","admin/catalog/models/"+race_id+"/draft",
            pair[1].model_dump(mode="json")),zip((owner_client,operator_client),race_commands)))
    check(sorted(status for status,_ in race_results)==[200,409],"catalog_initial_create_race")

    initial=connection(); path="admin/catalog/connections/"+CONNECTION+"/draft"
    status,receipt=call(operator_client,"POST",path,initial.model_dump(mode="json"))
    check(status==200 and receipt["result_version"]==1,"catalog_connection_draft")
    cred=credential(operator["password"])
    status,binding=call(operator_client,"POST","admin/catalog/connections/"+CONNECTION+"/credentials",
        {**cred.model_dump(mode="json"),"current_password":operator["password"]})
    check(status==200 and binding["version"]==1 and "IZO_FAL_KEY" not in json.dumps(binding),"catalog_credential_binding")
    first_cap=capability(); check(call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/draft",
        first_cap.model_dump(mode="json"))[0]==200,"catalog_capability_draft")

    commands=[capability(expected=1,name="Concurrent A"),capability(expected=1,name="Concurrent B")]
    clients=[owner_client,operator_client]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda pair:call(pair[0],"POST","admin/catalog/models/"+CAPABILITY+"/draft",
            pair[1].model_dump(mode="json")),zip(clients,commands)))
    check(sorted(status for status,_ in results)==[200,409],"catalog_capability_version_race")

    proof_payload=ProofInput(operation_id=uuid4(),expected_version=2,connection_id=CONNECTION,
        connection_version=2,reason="offline catalog proof").model_dump(mode="json")
    status,proof=call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/proof",proof_payload)
    check(status==200 and not proof["network_called"] and not proof["live_ready"],"catalog_offline_proof")
    check(call(operator_client,"POST","admin/catalog/connections/"+CONNECTION+"/publish",
        PublishInput(operation_id=uuid4(),expected_version=2,proof_id=UUID(proof["proof_id"]),
                     reason="publish disabled connection").model_dump(mode="json"))[0]==200,"catalog_publish_connection")
    check(call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/publish",
        PublishInput(operation_id=uuid4(),expected_version=2,proof_id=UUID(proof["proof_id"]),
                     reason="publish capability metadata").model_dump(mode="json"))[0]==200,"catalog_publish_capability")

    check(call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/draft",
        capability(expected=3,name="Next draft").model_dump(mode="json"))[0]==200,"catalog_next_draft")
    stale_status,stale=call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/proof",
        ProofInput(operation_id=uuid4(),expected_version=4,connection_id=CONNECTION,
            connection_version=3,reason="proof before rotation").model_dump(mode="json"))
    check(stale_status==200,"catalog_pre_rotation_proof")
    rotated=credential(operator["password"],expected=3,version=2)
    status,rotation=call(operator_client,"POST","admin/catalog/connections/"+CONNECTION+"/credentials",
        {**rotated.model_dump(mode="json"),"current_password":operator["password"]})
    check(status==200 and rotation["version"]==2,"catalog_rotation")
    stale_publish=PublishInput(operation_id=uuid4(),expected_version=4,proof_id=UUID(stale["proof_id"]),
        reason="must reject stale proof").model_dump(mode="json")
    check(call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/publish",stale_publish)[0]==409,
          "catalog_rotation_stales_proof")
    current_status,current_proof=call(operator_client,"POST","admin/catalog/models/"+CAPABILITY+"/proof",
        ProofInput(operation_id=uuid4(),expected_version=4,connection_id=CONNECTION,
            connection_version=4,reason="proof after rotation").model_dump(mode="json"))
    check(current_status==200,"catalog_current_proof")
    revoke=RevokeCredential(operation_id=uuid4(),expected_version=4,reason="isolated revoke",
        current_password=operator["password"])
    check(call(operator_client,"POST","admin/catalog/connections/"+CONNECTION+"/credentials/revoke",
        {**revoke.model_dump(mode="json"),"current_password":operator["password"]})[0]==200,"catalog_revoke")

    status,model=call(operator_client,"GET","admin/catalog/models/"+CAPABILITY)
    status2,conn=call(operator_client,"GET","admin/catalog/connections/"+CONNECTION)
    check(status==status2==200 and model["published"] is not None and not model["runtime_available"],"catalog_model_http")
    check(conn["runtime_state"]=="disabled" and conn["credential"] is None,"catalog_connection_disabled")
    check(call(operator_client,"GET","admin/catalog/connections/"+CONNECTION+"/credential")[0]==404,"catalog_revoked_hidden")
    check(call(ordinary,"GET","admin/catalog/models")[0]==403,"catalog_ordinary_denied")
    invalid=initial.model_dump(mode="json")|{"endpoint":"https://evil.invalid","runtime_state":"active"}
    status,body=call(operator_client,"POST",path,invalid)
    check(status==422 and "evil.invalid" not in json.dumps(body),"catalog_endpoint_injection_denied")
    immutable(auth.engine)
    check(job_catalog.capability(job_catalog.FAL_CAPABILITY).version=="fal-klein4b-1","catalog_runtime_unchanged")
    cleanup_bootstrap_owner(auth,UUID(owner["id"]))
    print("CATALOG_BEFORE_OK: ACCESS provisioning, PG race, offline proof, disabled publish, rotation/revoke, immutable history",file=sys.stderr)
    return {"operator":operator,"connection_command":initial.model_dump(mode="json"),
            "published_model_hash":model["published"]["content_hash"],
            "published_connection_hash":conn["published"]["content_hash"],
            "proof_id":current_proof["proof_id"]}


def after(auth,state):
    operator=state["operator"]
    client=Client(auth.policy.cookie_name,operator["raw"]); client.csrf=operator["csrf"]
    status,model=call(client,"GET","admin/catalog/models/"+CAPABILITY)
    status2,conn=call(client,"GET","admin/catalog/connections/"+CONNECTION)
    check(status==status2==200,"catalog_http_after_restart")
    check(model["published"]["content_hash"]==state["published_model_hash"],"catalog_model_persisted")
    check(conn["published"]["content_hash"]==state["published_connection_hash"],"catalog_connection_persisted")
    check(conn["runtime_state"]=="disabled","catalog_never_activated")
    check(call(client,"GET","admin/catalog/connections/"+CONNECTION+"/credential")[0]==404,"catalog_revocation_persisted")
    command=ConnectionDraft.model_validate(state["connection_command"])
    replay=CatalogService(auth).save_connection(client.raw,client.csrf,CONNECTION,command)
    check(replay.operation_id==command.operation_id and replay.result_version==1,"catalog_replay_after_restart")
    with auth.engine.begin() as db:
        check(db.execute(sa.select(sa.func.count()).select_from(t.capability_revisions)).scalar_one()==4,
              "catalog_capability_history_persisted")
        check(db.execute(sa.select(sa.func.count()).select_from(t.proofs)).scalar_one()==3,
              "catalog_proofs_persisted")
    check(job_catalog.capability(job_catalog.FAL_CAPABILITY).version=="fal-klein4b-1","catalog_runtime_still_unchanged")
    print("CATALOG_AFTER_OK: hashes/history/revocation/replay persisted; Jobs/Fal runtime unchanged",file=sys.stderr)


def main():
    if os.getenv("IZO_ENVIRONMENT")!="test" or os.getenv("IZO_CATALOG_ACCEPTANCE")!="isolated":
        raise SystemExit("Disposable isolated test stack only")
    auth=AuthService(create_auth_engine(Settings()),AuthSettings())
    try:
        if sys.argv[1:]==["before"]: json.dump(before(auth),sys.stdout)
        elif sys.argv[1:]==["after"]: after(auth,json.load(sys.stdin))
        else: raise SystemExit("Expected before or after")
    except Exception as exc:
        print("CATALOG_ACCEPTANCE_FAILED: "+type(exc).__name__,file=sys.stderr)
        if isinstance(exc,AssertionError): print(str(exc),file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        auth.engine.dispose()


if __name__=="__main__": main()

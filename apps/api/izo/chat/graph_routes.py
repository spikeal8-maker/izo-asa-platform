"""Additive Graph HTTP projection and same-origin owner commands."""
from uuid import UUID

from fastapi import Query, Request

from .branches import branch_page, change_branch
from .graph_requests import admit_request
from .graph_schemas import GraphAttemptPage, GraphPage, GraphRegenerate
from .graph_schemas import GraphRequestAccepted, GraphSelection, GraphTurnState
from .graph_schemas import BranchEdit, BranchEditView, BranchPage, BranchSelection
from .graph_selection import change_selection
from .history_pages import attempt_page, graph_page


def attach_graph_routes(router, runtime_service, bearer, mutation):
    @router.get("/threads/{thread_id}/graph", response_model=GraphPage)
    def graph(thread_id: UUID, request: Request,
              before_turn_sequence: int | None = Query(default=None, ge=1, le=9223372036854775807),
              branch_id: UUID | None = Query(default=None)):
        service = runtime_service(request)
        return graph_page(service, bearer(request, service), thread_id, before_turn_sequence, branch_id)

    @router.get("/threads/{thread_id}/turns/{turn_id}/attempts", response_model=GraphAttemptPage)
    def attempts(thread_id: UUID, turn_id: UUID, request: Request,
                 before_ordinal: int | None = Query(default=None, ge=1, le=9223372036854775807),
                 branch_id: UUID | None = Query(default=None)):
        service = runtime_service(request)
        return attempt_page(service, bearer(request, service), thread_id, turn_id, before_ordinal, branch_id)

    @router.get("/threads/{thread_id}/branches", response_model=BranchPage)
    def branches(thread_id: UUID, request: Request,
                 before_branch_ordinal: int | None = Query(default=None, ge=1, le=9223372036854775807)):
        service = runtime_service(request)
        return branch_page(service, bearer(request, service), thread_id, before_branch_ordinal)

    @router.patch("/threads/{thread_id}/branch-selection", response_model=GraphPage)
    def branch_selection(thread_id: UUID, data: BranchSelection, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return change_branch(service, raw, csrf, thread_id, data)

    @router.post("/threads/{thread_id}/turns/{source_turn_id}/edit", response_model=BranchEditView, status_code=202)
    def edit(thread_id: UUID, source_turn_id: UUID, data: BranchEdit, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return admit_request(service, raw, csrf, thread_id, data, source_turn_id, edit=True)

    @router.post("/threads/{thread_id}/turns/{turn_id}/regenerate",
                 response_model=GraphRequestAccepted, status_code=202)
    def regenerate(thread_id: UUID, turn_id: UUID, data: GraphRegenerate, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return admit_request(service, raw, csrf, thread_id, data, turn_id)

    @router.patch("/threads/{thread_id}/turns/{turn_id}/selection", response_model=GraphTurnState)
    def selection(thread_id: UUID, turn_id: UUID, data: GraphSelection, request: Request):
        service = runtime_service(request)
        raw, csrf = mutation(request, service)
        return change_selection(service, raw, csrf, thread_id, turn_id, data)

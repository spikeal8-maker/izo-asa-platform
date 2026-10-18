# Project state: live GitHub evidence transports

Owners: `tools/project_state.py` and `tools/project_state_closeout.py` select the target checkout and transport;
`project_state_evidence.py` keeps the existing evidence contract;
`project_state_connector.py` owns REST collection and the final write barrier;
`project_state_rest_checks.py` validates REST protection/check identity;
`github_connector_bridge.py` owns the bounded controller channel.

## Selection and trusted boundary

`gh` remains the default. The explicit alternative is:

```sh
python /reviewed/tooling/tools/project_state.py \
  --repo-root /clean/target/checkout --github-transport connector-stdio \
  begin-decided-next --branch <next-branch> --activate <package-id> \
  --goal '<bounded goal>' --depends-on <source-package> --decides-next \
  --verified-pr <source-pr>
```

The standalone terminal-closeout entrypoint uses the same options and live protocol:

```sh
python /reviewed/tooling/tools/project_state_closeout.py \
  --repo-root /clean/source/checkout --github-transport connector-stdio \
  --branch state/<package>-complete --verified-pr <source-pr>
```

Global options precede the `project_state.py` subcommand; the standalone closeout has
no subcommand. Without `--repo-root`, the script's repository
is the target. An explicit root must be the exact Git checkout root; state, scopes,
registry, checkpoints, Git reads and writes all use it. This allows independently
reviewed tooling to operate an earlier clean source checkout without injecting files,
changing imports or modifying canonical state by hand. The usual branch/source,
dependency, review, CI and transition requirements still apply.

Closeout starts at the exact source PR head, including when that PR is already merged.
It preserves canonical lineage and the active package identity, records the accepted
source checkpoint, and sets the package to terminal `complete` without a successor.
For a merged source, both entrypoints reuse authenticated pre-merge review/owner-waiver
evidence; explicit post-merge waiver flags are rejected. A later successor from an
accepted merged closeout still requires its separate PR, push-CI and immutable
checkpoint provenance under the existing terminal lifecycle.

`connector-stdio` trusts the local controller to call the authorized GitHub Connector
and relay the complete fresh result of that exact call. Request nonces, digests and
timeouts protect correlation and accidental replay; **they are not GitHub signatures
and cannot authenticate a dishonest controller**. Retain the controller's actual tool
call transcript with the transition output for review. Never label self-supplied JSON,
an offline snapshot, a test fixture or a controller-edited response as live evidence.
There is no evidence-file importer, offline mode, credential exchange, `gh` shim or
automatic fallback. The selected transport changes collection, not owner authority.

## Controller JSONL protocol

Use a subprocess with stdin/stdout pipes, UTF-8 and no terminal echo or canonical line
limit. Each stdout line beginning `IZO_GITHUB_REQUEST ` contains one JSON request:

```json
{"protocol":"izo-github-connector-v1","repository":"owner/repo","operation":"rest_get","params":{"endpoint":"repos/owner/repo/branches/main"},"request_id":"<random>","nonce":"<random>","ttl_seconds":180,"request_digest":"<sha256>"}
```

For each new request the controller performs exactly the indicated read, checks tool
success/completeness, then writes one response JSON line to stdin. It copies `protocol`,
`repository`, `operation`, `request_id`, `nonce`, `request_digest` from that request and
adds `ok: true`, `tool` from the table, and `payload` containing the raw result below.
The request digest is SHA-256 of the request before adding `request_digest`, encoded
with Python-compatible sorted JSON keys, ASCII escapes and compact separators.
Do not compute or normalize API fields on behalf of validators.

| Operation | Actual Connector tool | Arguments and raw payload |
| --- | --- | --- |
| `rest_get` | `github_fetch` | `url = https://api.github.com/` + `params.endpoint`; decoded raw GitHub JSON object/array |
| `job_log` | `github_fetch_workflow_job_logs` | `repo_full_name = repository`, `job_id = params.job_id`; complete decoded log string |
| `current_user` | `github_get_user_login` | `{}`; raw object with `login` and user ID |

The controller unwraps only the tool's documented result envelope. It must refuse
truncated/error results and must not extract a substring of a job log. A failed tool
call gets a matching `ok: false` response, or the pipe closes; neither permits a
transition. Responses are limited to 16 MiB and 180 seconds per request. Missing/wrong
identity, nonce, digest or tool, EOF, invalid JSON, expired/replayed response or changed
observations fail the invocation. Resume by a new invocation with fresh reads after
resolving the specific failure; do not manufacture a successful response.

Only the repository-scoped read endpoints required by the state owners are permitted.
Pagination is performed by the CLI, with explicit page numbers and `per_page=100`,
complete total-count checks for object collections, terminating short pages for list
collections, duplicate-ID detection, and bounded collection sizes. The controller
must not substitute a convenient first-page wrapper for an emitted page request.

## REST required-check proof

The proof has its own `github_rest_required_checks_v1` kind. It does not fabricate a
GraphQL rollup or `isRequired`. Both OPEN and MERGED source PR paths require it when
Connector is selected. The current bounded contract requires:

- Exact source PR number, repository, branch, base and SHA identities.
- Protected `main`, enabled classic protection enforced for everyone, matching real
  `contexts` and app-bound `checks`, and a complete repository/inherited ruleset list.
  Only an empty ruleset list is supported. Any rule requires an independently reviewed
  extension; a missing/forbidden/incomplete protection response cannot imply success.
- Complete check-run **and separate check-suite** enumeration, each below 1,000. This
  explicitly excludes the API's 1,000-suite truncation boundary; run count alone is
  insufficient. Every actual check/status context must succeed. An empty legacy
  status list with `total_count=0` may report aggregate `pending`; no legacy context
  exists in that case. A foreign queued suite with no actual check-run is likewise
  only a container, not an invented pending check context.
- Required job names bound to actual protection app IDs, exact check-run IDs, suite
  IDs, selected workflow IDs/paths, source SHA/branch, event, and latest run attempt.
  Jobs are fully paginated with `filter=latest`, then checked against run ID, attempt,
  source SHA and `check_run_url`. A newer failed/pending run cannot be hidden behind
  an earlier success or omitted second page.
- Foundation's unique tested `IZO_BUILD_SHA` read from complete logs of all jobs in
  the selected run/attempt. Existing merge parent/tree equality and pre-merge time
  checks remain authoritative. The tested merge commit can differ from both source
  HEAD and the actual merge commit while their tested trees correctly match.
- Existing structured independent review or exact-SHA owner waiver predicates,
  including complete review/comment pagination and pre-merge creation/update time.
  A historical source checkpoint may have a later current main; exact current-main
  equality stays at the merged-source bootstrap/closeout owner, not the generic proof.

Before writing, both CLI entrypoints re-read every mutable observation and reject any changed
payload. It then checks origin, exact canonical-main/tested-merge Git ref where
applicable, and target HEAD/branch/cleanliness immediately before the existing atomic
transition. Its rollback behavior and checkpoint format are preserved. No GitHub
write, merge or deployment is part of this transport.

## Verification

Focused tests are `test_github_connector_bridge.py`, `test_project_state_connector.py`,
`test_project_state_rest_checks.py`, `test_project_state_transport_root.py`, and the
existing project-state/review suites. Fixtures are explicitly synthetic. Git checkout
tests cover both begin commands and terminal closeout, default `gh` routing, valid external
tooling root, pre-merge structured review/owner waiver, stale/ref/checkout drift, and
byte-for-byte preservation of state and absence of a new branch on failure.
Local tests establish implementation behavior; an actual live Connector transition,
required CI and independent review remain separate evidence.

# Platform provider registry · B1

Separate staff-governed platform credential **metadata and encrypted storage**.
This module never creates a second Chat execution path and never exposes credentials
in a response. Existing BYOK accounts, Chat requests, Graph and Catalog are unchanged.
The initial DeepSeek connection is **not yet offered to users**:
\`available_to_users=false\` is intentionally unconditional until the audited
P0-C routing/admission/budget package. Enabling here records operator intent only.

Auth and permissions remain in Accounts: \`connections.read\` for read;
\`connections.write\` plus \`secrets.bind\` and password reauthentication for
key replacement/verification; \`connections.write\` for policy changes.
Admin append-only events record change metadata, not secret contents.
Only fixed DeepSeek adapter in test/development; fake provider in test.
Owner credentials are never inferred from \`preview@local.izo\`.

B1: one encrypted row, exact UUID replay, optimistic revision CAS, audit,
fixed model/budget bounds, synthetic verification, UI.
B2/C: account-level admission, paid cost/fleet limits, routing, provider
draining, secure live verification policy and real-model browser acceptance.

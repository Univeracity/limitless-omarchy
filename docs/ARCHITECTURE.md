# Architecture

## Intent

The Omarchy integration is a thin receiver adapter over Limitless Library. It
does not define a new reuse protocol and does not turn the desktop into a
service client by default.

## Local lifecycle

    Agent or owner states the intended customization
                     |
                     v
    Derive a minimal Omarchy receiver profile
                     |
                     v
    Query eligible local Work Capsules using local-only intent
                     |
                     v
    Exact component / source-free method / abstain
                     |
                     v
    Review and use Omarchy native validation and enablement
                     |
                     v
    Local adoption evidence
                     |
                     v
    Compact method registration under saved owner policy

The receiver profile intentionally contains only platform, plugin schema,
explicit release, and shell IPC availability. It does not enumerate installed
plugins or read arbitrary user configuration. The short objective is bound to
the local query and never leaves the machine during local reuse.

## Local method registration

The Omarchy-aware MCP server exposes a compact mutating tool after its query
tool. An agent supplies only `name` and `steps`; `summary`, `verify`, `sources`,
`taskKind`, and `supersedes` are optional. Limitless normalizes and bounds the
input, creates an opaque time-sortable reference, content digest, immutable
record, lineage, and sealed local catalog projection, then returns only status,
reference, and destination. Duplicate content is idempotent and does not add a
record or echo method contents into the agent context. Duplicate detection is
limited to current revisions, so historical content cannot masquerade as an
available method. Records are revalidated against their content digests and
filename-bound references on every read.

Mutable sharing state is stored separately from immutable method records.
Supersession removes only the old local catalog projection; it retains every
record and public release reference. The local catalog uses a short objective
only as a conservative lexical tie-break between otherwise-equal eligible
offers. Rights, compatibility, scope, and explicit priority remain controlling;
an unmatched or tied result abstains.

The older explicit sealing command remains available for owner-provided exact
or method Capsule drafts. It delegates digesting, schema validation, and
immutable output creation to Limitless Library and never scans a workspace.

## Native surface

The Quattro panel is a standalone third-party panel with a paired bar widget,
so an enabled plugin has a visible UI entry point. It owns the normal local
setup and query flow: an explicit panel action creates an isolated runtime
under `XDG_DATA_HOME` and installs the reviewed adapter and public Library core
there. Before changing that runtime, setup verifies the committed lock and both
pure-Python wheels against their release-manifest SHA-256 digests. It installs
the complete dependency graph with hashes required and binary distributions
only, then installs the local wheels with no index or dependency resolution.
No Git checkout or package build runs during user setup. The same explicit action reconciles a local MCP entry
for the agent Omarchy currently selects as its default. It never modifies the
system Python or makes a service connection.

Agent connection is independent per target. The panel reads the host-owned
default-agent selection, treats it as the first target, and allows the owner to
add optional Omarchy agent IDs. Codex, Claude Code, and Grok adapters delegate
to their own MCP commands; the Antigravity CLI adapter uses its documented
standalone user profile. Every adapter verifies the resulting exact descriptor.
The local state file identifies only a plugin-owned server name and exact
command/args; on a later reconcile or disconnect, a changed or colliding entry
is reported and left untouched. Unsupported or unavailable clients produce a
local report without preventing other targets from being connected. No prompt,
workspace content, catalog contents, or service credential appears in that
state.

The panel invokes a bundled runtime script rather than assuming the companion
CLI exists on `PATH`. The script accepts an explicit plugin-root argument,
requires an absolute XDG data directory, and exposes `status`, `setup`,
`query`, `agent-status`, `agent-reconcile`, `agent-disconnect`,
`stats`, `settings-show`, `settings-apply`, `draft-list`, `register-method`,
`contribution-sync`, `contribution-transition`, `service-activate`, `service-inspect`, `service-query`,
`service-artifact-stage`, `service-artifact-review`,
`service-artifact-install`, `service-artifact-enable`, and
`service-publication` actions. Installer output is confined to the XDG runtime,
so setup never mutates Omarchy's recursively watched plugin checkout or
triggers a desktop hot reload.
Service activation is one explicit UI action and uses only trust material
pinned in the installed public Library release; ordinary users never manage a
profile path or API key. Setup is never automatic. The runtime owns one default
catalog beneath its XDG data root; power-user path selection remains a
lower-level CLI concern and is not part of the panel.

No UI path silently installs or enables a customization. Sharing follows the
owner's saved destination and contribution mode; only Automatic + Public is a
standing authorization for silent transfer of qualifying source-free methods.
An exact
managed result keeps its delivery capability in owner-only installation-signed
state; the panel can redeem that state into digest-verified staging without
retaining the objective. The explicit Omarchy receiver adapter accepts only the
signed `limitless.exact-file-bundle/1.0` descriptor, parses the canonical
bundle, materializes a digest-named owner-only review tree without overwrite,
reverifies its complete file inventory, and invokes only
`omarchy plugin validate <review-tree>`.

After a successful review, **Install reviewed plugin disabled** is a separate
owner action. It copies the same verified bytes without overwrite into
Omarchy's user plugin directory, rescans the native registry, proves the exact
plugin is discovered and disabled, and writes signed owner-only installation
state. It refuses an existing plugin id or an id already referenced by
`shell.json`; it never executes an install hook or invokes plugin code.

**Enable reviewed plugin** is another separate owner action. It reloads and
reverifies the exact installed inventory and signed installation state before
calling Omarchy's fixed-argument native enable operation. The adapter then
requires the native registry and persisted shell configuration to agree. For
summonable plugins it also invokes the plugin through Omarchy shell IPC; for
eagerly loaded widget and service kinds, successful native enablement is the
runtime invocation event. A signed local adoption receipt binds the original
decision, exact bundle, installed path, native runtime projection, and observed
invocation. Full-bar replacement is excluded because it has no ordinary
disabled-to-enabled transition and changes the desktop's controlling bar.

The normal companion MCP surface provides three tools through one plugin-owned
connection. `limitless_query_before_work` accepts the standard core receiver
envelope for general work. `omarchy_query_before_customization` derives the
minimal Omarchy receiver profile from a concise objective already present in
the calling agent's context. `limitless_register_method` records compact useful
methods under saved owner policy. The convenience query may accept an explicitly
known Omarchy release; its task kind and tenant scope remain fixed to Omarchy
customization and private reuse.

## Contribution lifecycle

Owner settings separate destination (`off`, `local`, `circle`, `organization`,
or `public`), initiator (`manual`, `agent-mediated`, or `automatic`), and
material policy. Public is accepted only with the currently verified signed
publication-policy digest. Automatic + Public binds standing authorization to
that exact digest.

Registration is always a fast local transaction. Public work is projected into
a CC0 source-free method plus a bounded publication draft and sent by a
detached, non-blocking worker. Local filesystem references stay local; only
HTTPS source references can appear in public method material. The worker uses
owner-only resumable state, retries service failures without changing the agent
result, never republishes an existing remote state when a status check fails,
and pauses on policy drift until the owner reauthorizes the new digest.

Per-method transitions mutate only the sharing projection. Moving a submitted
or active public method inward queues revocation before reaching its target
state. Registry and sharing locks serialize an owner transition with revision
creation and the background worker. Superseded pending releases continue
through remote status resolution;
a new revision waits for that result and, when available, binds the prior public
release as its parent and superseded release. Superseded revisions cannot be
moved back into circulation.

## Advanced generic-only provider

`limitless-omarchy provider --catalog …` is a separate, explicit local MCP
entry point for an owner who wants a generic-only connection against another
catalog. It wraps the pinned Limitless Library stdio server
only to increment an aggregate outcome counter; the generic tool, framing,
schemas, session behavior, and policy remain owned by the core rather than
copied into this adapter.

This entry point does not call the Omarchy profile adapter, inspect desktop
state, or combine catalogs. The default `mcp` entry point already supports
both general and Omarchy-specific queries; the separate provider is optional
lower-level control, not a prerequisite for general reuse.

## Local activity projection

The panel-owned runtime maintains one bounded XDG-scoped activity file for its
**Stats** tab. It distinguishes Omarchy-specific local queries,
Omarchy-specific managed queries, and opt-in general Limitless queries. It also
counts result classes and explicit lifecycle operations. The file contains no
objectives, prompts, paths, identifiers, capsule metadata, or result content;
it is local presentation state, not adoption evidence or service history.
Updates are best-effort under an advisory lock and use an owner-only atomic
replacement. An unavailable, malformed, oversized, or symlinked stats file is
reported as unavailable and never repaired by overwriting it during an
ordinary operation. Stats failure cannot change a query or lifecycle result.

## Opt-in service boundary

The panel keeps query and connection actions in **Library**. **Service** is the
projection for anonymous installation identity, usage and quota, future account
or organization state, upgrade paths, and expandable trust details. A supported Library release bundles an immutable locator
containing the exact profile
digest and URL, service identity, and original Ed25519 root. Activation fetches
and verifies that profile, the root-transition chain, signed discovery, and the
accepted policy before storing credential-free XDG-scoped state. No endpoint
is discovered implicitly and ordinary panel startup never makes a service
request. Source builds without a locator remain local-only.

The same owner action creates a service-specific Ed25519 installation key,
verifies the service's signed attestation, and opens the anonymous baseline
session used by the UI. The key and short-lived bearer are stored separately
from activation state in an owner-only file. The ordinary UI never asks the
user to choose protocol capabilities or paste a credential.

Inspection verifies root transitions and signed discovery without submitting
an objective. A query sends one explicit objective and the minimal receiver
context over the public Limitless service contract. The objective travels to
the panel-owned process over bounded stdin and is cleared after dispatch; it is
not written to argv or disk. The adapter returns only a verified signed
decision or an explicit availability abstention. Trust or policy failures are
errors, not abstentions.

An explicit `--profile` option remains in the lower-level CLI for another
owner-reviewed compatible service. It is not exposed in ordinary panel setup
and cannot redefine the release-pinned official identity.

The private service owns identity, policy evaluation, scopes, grants,
revocation, ranking, persistence, and managed coordination. The plugin works
without those facilities and never makes connection imply capture,
publication, installation, or enablement.

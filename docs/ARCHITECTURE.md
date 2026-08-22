# Architecture

## Intent

The Omarchy integration is a thin receiver adapter over Limitless Library. It
does not define a new reuse protocol and does not turn the desktop into a
service client by default.

## Local lifecycle

    Agent or owner requests a customization
                     |
                     v
    Derive a minimal Omarchy receiver profile
                     |
                     v
    Query eligible local Work Capsules
                     |
                     v
    Exact component / source-free method / abstain
                     |
                     v
    Review and use Omarchy native validation and enablement
                     |
                     v
    Local adoption evidence

The receiver profile intentionally contains only platform, plugin schema,
explicit release, and shell IPC availability. It does not enumerate installed
plugins, read arbitrary user configuration, or export task text.

## Local capsule authoring

The adapter provides an explicit sealing command for an owner-provided Capsule
draft. It delegates digesting, schema validation, and immutable output creation
to Limitless Library. It does not inspect an agent session, infer a sharing
scope, add a capsule to a catalog, or publish anything. Those remain owner
actions.

## Native surface

The Quattro panel is a standalone third-party panel with a paired bar widget,
so an enabled plugin has a visible UI entry point. It owns the normal local
setup and query flow: an explicit panel action creates an isolated runtime
under `XDG_DATA_HOME` and installs this reviewed adapter plus its pinned public
Library dependency there. It never modifies the system Python, requires MCP
configuration, or makes a service connection.

The panel invokes a bundled runtime script rather than assuming the companion
CLI exists on `PATH`. The script accepts an explicit plugin-root argument,
requires an absolute XDG data directory, and exposes `status`, `setup`,
`query`, `query-demo`, `service-activate`, `service-inspect`, `service-query`,
`service-artifact-stage`, `service-artifact-review`,
`service-artifact-install`, `service-artifact-enable`, and
`service-publication` actions.
Service activation is one explicit UI action and uses only trust material
pinned in the installed public Library release; ordinary users never manage a
profile path or API key. Setup is never automatic. A caller can still prefill a
catalog path in a summon payload, or enter one through the panel UI.

No UI path silently installs, enables, or shares a customization. An exact
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

The companion also provides an Omarchy-aware local MCP tool. It derives the
same minimal receiver profile before calling the generic Library decision
layer. The MCP input does not admit arbitrary task text or configuration;
agents may provide only an explicitly known Omarchy release. Task kind and
tenant scope are fixed to Omarchy customization and private reuse.

## Optional general provider

`limitless-omarchy provider --catalog …` is a separate, explicit local MCP
entry point for an owner who wants this installation to provide general
Limitless reuse as well. It replaces itself with Limitless Library's generic
stdio server, so the generic tool, framing, schemas, and policy remain owned
by the core rather than copied into this adapter.

This entry point does not call the Omarchy profile adapter, inspect desktop
state, or combine catalogs. It exists to eliminate duplicate package and MCP
configuration for an owner who has deliberately chosen a general local
catalog. The default `mcp` entry point remains bounded to private
Omarchy-customization requests.

## Opt-in service boundary

The panel exposes a separate, collapsed managed-service section. A supported
Library release bundles an immutable locator containing the exact profile
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

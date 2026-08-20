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
`query`, `query-demo`, `service-inspect`, and `service-query` actions. The
service actions remain unreachable until the owner supplies an absolute
profile path and explicitly invokes one. Setup is never automatic. A caller
can still prefill a catalog path in a summon payload, or enter one through the
panel UI.

No UI path silently installs, enables, or shares a customization. Exact
components remain subject to Omarchy's native Git installation, validation,
review, and explicit enablement flow.

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

The panel exposes a separate, collapsed managed-service section. It requires
an owner-supplied profile containing the exact HTTPS endpoint, service
identity, pinned Ed25519 root, accepted policy digest, data-use mode, and
maximum scopes. No endpoint is discovered implicitly and ordinary panel
startup never makes a service request.

Inspection verifies root transitions and signed discovery without submitting
an objective. A query sends one explicit objective and the minimal receiver
context over the public Limitless service contract. The optional bearer token
travels from the masked UI field to the panel-owned process over stdin and is
cleared with the objective after dispatch; neither is written to argv,
environment, profile, or disk. The adapter returns only a verified signed
decision or an explicit availability abstention. Trust or policy failures are
errors, not abstentions.

The private service owns identity, policy evaluation, scopes, grants,
revocation, ranking, persistence, and managed coordination. The plugin works
without those facilities and never makes connection imply capture,
publication, installation, or enablement.

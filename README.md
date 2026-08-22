# Limitless Library for Omarchy

Local-first verified reuse for Omarchy customizations and, when explicitly
enabled, general local agent work.

Before an agent creates a new customization, this adapter lets it ask whether
one owner-authorized prior result is eligible for the current Omarchy receiver.
It returns one exact component, one source-free method, or a safe abstention.

This repository contains a native Quattro panel, its companion CLI, and an
opt-in client for the public managed-service wire contract. It is not an
Omarchy plugin directory or package manager.
Omarchy's Git-based plugin ecosystem remains responsible for ordinary public
plugin distribution.

## What is different

Most useful Omarchy work will never be polished into a public plugin. A recent
agent-created panel adjustment, workflow, or local integration can still become
a private Work Capsule. The Library can consult eligible capsules before more
arbitrary work is created, while the owner retains control over capture and
sharing.

Public Omarchy Plugins are one possible source of exact components. They are
not a prerequisite for local capture, local reuse, private cross-device reuse,
or a source-free method.

## Local-first boundary

The adapter works without a Limitless account or service connection. Its panel
runtime and optional companion CLI:

- derives only a minimal receiver profile;
- does not inspect the user's plugin list, arbitrary desktop configuration,
  prompts, screenshots, command history, or agent workspace;
- does not silently install or enable a plugin; and
- leaves decisions and evidence local.

The managed Limitless implementation remains outside this repository. A
supported release can pin its official service identity, trust root, profile,
and policy in the public Library dependency. Enabling it is always explicit.
Connecting never publishes local work; capture and sharing remain separate
actions.

## Use it from Omarchy

Add and enable the reviewed repository through **Setup › Plugins**. The
Limitless Library `L` button will appear in the right side of the bar. Click
it, then select **Install local runtime**. The panel creates its own isolated
runtime beneath your XDG data directory; it does not alter the system Python,
require an agent, configure MCP, or connect to a service.

The first explicit setup needs Python 3 and network access to install the
pinned public Library dependency into that isolated runtime. Once complete,
the panel itself is the normal way to use Limitless Omarchy:

1. Click **Try included example** to inspect a fully local source-free method.
2. Paste an absolute path to an owner-controlled local catalog.
3. Click **Query local catalog** before a material customization.

Setup and query actions never install or enable a desktop change, capture a
session, or share work. They create the per-user runtime after the explicit
button press, query the catalog you select, and show a component, method, or
safe abstention. A compatible managed exact component exposes later, separate
review, install-disabled, and enable actions; none is inferred from the query.

## Optional managed service from the panel

Local use is always available without a service connection. Open **Use
Limitless service (optional)** and select **Enable official service**. That one
action fetches the exact release-pinned, credential-free profile and verifies
the service identity, original root, root-key history, policy digest, protocol,
and result keys before saving activation state. It then creates one private,
service-specific installation key and obtains a short-lived anonymous session.
No account, profile download, API key, terminal, or agent setup is required. A
build without published official trust material stays local-only.

After inspection, enter one customization objective and select **Query managed
service**. The panel sends that objective plus the minimal Omarchy receiver
context under the activated audience and history boundary. The objective is
sent to the panel-owned process over bounded stdin and cleared after dispatch;
it is never placed in argv or a local file by the plugin.

The result must be signed, current, bound to the exact query, policy-compatible,
and receiver-compatible before the panel displays it. Service unavailability
returns control to local reuse. Inspecting or querying never installs a plugin,
captures local work, uploads a catalog, or enables sharing.

When an exact artifact is selected, the panel saves its delivery authority only
inside an owner-only, installation-signed continuation; the visible result does
not contain that capability. **Prepare verified plugin review** redeems the
continuation into a new digest-verified owner-only file, requires the signed
portable exact-file-bundle descriptor, materializes its canonical file tree
without overwrite, and runs `omarchy plugin validate` against that tree. The
objective is not retained. The panel displays the receiver-owned review path
and native result. If validation succeeds, **Install reviewed plugin disabled**
copies those same exact bytes without overwrite into Omarchy's user plugin
directory, rescans the native registry, and refuses to continue unless Omarchy
reports the plugin as disabled. It saves a signed local installation state.
**Enable reviewed plugin** is a second explicit action: it reverifies the
installed inventory, asks Omarchy to enable it, confirms persisted native
enablement, observes the plugin through Omarchy's runtime, and saves a signed
local adoption receipt. Full-bar replacements fail closed because they do not
have the ordinary disabled-to-enabled lifecycle.

Public contribution is a separate, explicit panel action. Open **Share a
reviewed contribution (optional)**, select one absolute path to a reviewed
`limitless.publication-draft/1.0` file, inspect and accept the currently
advertised policy for that submission, and select **Publish explicitly selected
draft**. The panel binds that acceptance to the exact signed policy digest it
displayed and refuses the submission if the service advertises a different
digest. The draft itself names every regular file that may be considered;
Limitless never scans the workspace or infers additional sources. The panel
uploads only missing, digest-bound objects and saves owner-only resumable state
beside the draft. That state can later check admission status or withdraw an
active release from the same panel. Withdrawal requires a second confirmation.

Omarchy currently opens a terminal for its third-party-plugin Add flow so that
its review warning and clone output remain visible. That host-controlled step
precedes this plugin. No terminal or agent-side setup is required to operate
Limitless once the plugin has been reviewed and enabled.

## Optional command-line control

The CLI remains available for development, automation, diagnostics, and MCP
clients; it is not a prerequisite for the panel. Install it directly when you
want that lower-level control. Its pinned public Limitless Library dependency
is fetched automatically:

    python3 -m pip install .

For offline development against a local Limitless Library checkout, install
that checkout first and then install this project with no dependency resolution:

    python3 -m pip install /path/to/limitlesslibrary
    python3 -m pip install --no-deps -e .

## Companion CLI

Inspect the minimal local receiver profile:

    limitless-omarchy status

Query a local Library catalog before a customization:

    limitless-omarchy query --catalog ./examples/catalog

Validate this plugin using Omarchy's own validator:

    limitless-omarchy validate-plugin .

Enable and verify the release-pinned official service without sending a task:

    limitless-omarchy service-activate
    limitless-omarchy service-inspect

For a lower-level managed query, provide one
`limitless.omarchy-service-query-input/0.1` JSON line on stdin. Keeping the
objective on stdin prevents it from appearing in the process list:

    limitless-omarchy service-query \
      < /path/to/ephemeral-query-input.json

The panel's publish, status, and withdrawal actions use the same lower-level
`service-publication` command with one bounded
`limitless.omarchy-publication-input/0.1` JSON line on stdin. Paths and policy
acceptance therefore remain out of the process list. Direct CLI use is optional:

    limitless-omarchy service-publication \
      < /path/to/ephemeral-publication-input.json

Exact-artifact staging is likewise available as the optional
`service-artifact-stage` command. It accepts only one bounded
`limitless.omarchy-artifact-stage-input/0.1` JSON line on stdin; the ordinary
panel supplies the owner-only continuation path itself. The explicit receiver
adapter is available through `service-artifact-review`, using one bounded
`limitless.omarchy-artifact-review-input/0.1` JSON line. It performs staging,
exact-bundle materialization, inventory verification, and Omarchy-native
validation. `service-artifact-install` accepts a bounded
`limitless.omarchy-artifact-install-input/0.1` line and installs only that
reviewed handoff while proving it remains disabled. `service-artifact-enable`
accepts a bounded `limitless.omarchy-artifact-enable-input/0.1` line naming the
signed installation state; it enables only the reverified tree and emits
observed-invocation evidence. These commands are optional lower-level controls;
the panel owns the normal flow.

`--profile /absolute/path/to/owner-reviewed-profile.json` remains available on
inspection and query commands as advanced lower-level control for another
compatible service. It is not part of ordinary panel setup.

The local-catalog query returns a structured local-only result. An unavailable
catalog, missing core library, ambiguous candidate, or compatibility mismatch
produces an abstention rather than a best-effort selection. The service query
returns only a verified managed result or an explicit local-still-available
fallback.

The Omarchy-specific query surface is intentionally bounded to the
`omarchy-customization` task kind, private scope, and `adopt` or `instantiate`
use. It is not a general task-search client or a path for publishing a desktop
request.

## Preserve newly completed work locally

After an owner has reviewed a freshly completed customization, seal its
owner-provided Capsule draft without publishing it:

    limitless-omarchy seal-capsule \
      --draft ./my-capsule/capsule.draft.json \
      --output ./private-catalog/my-capsule/capsule.json

The output is digest-bound and refuses to overwrite an existing record. It
stays local until the owner deliberately places it in a different catalog or
sharing scope. For exact components, pass --root with the directory containing
the declared source files; methods default to the draft's directory.

## Connect an agent locally

Start the Omarchy-aware MCP server:

    limitless-omarchy mcp --catalog ./examples/catalog

It exposes one read-only tool, omarchy_query_before_customization. The tool
derives the minimal local receiver profile itself, so the agent does not need
to inspect or send arbitrary Omarchy configuration. This initial release fixes
the task kind and scope to Omarchy customization and private reuse; its only
other optional input is an explicitly known Omarchy release.

Use this as the agent's first material-customization step. It returns a
component, a source-free method, or an abstention; it never transports
artifact bytes or silently enables a desktop change.

## Optionally serve general Limitless reuse

The Omarchy tool above stays deliberately narrow. If the owner wants this one
installation to also be their **general local Limitless provider**, configure
the explicitly separate `provider` command:

    limitless-omarchy provider --catalog /absolute/path/to/general-catalog

It exposes the standard read-only `limitless_query_before_work` MCP tool from
Limitless Library. That tool accepts the generic Library query contract and
can serve ordinary agent reuse from the catalog the owner selected. It does
not derive or disclose an Omarchy profile, read desktop configuration, connect
to a service, or merge catalogs automatically.

The distinction is intentional: `limitless-omarchy mcp` remains the private,
Omarchy-aware first step for desktop customization, while `provider` is an
owner's explicit choice to expose general local reuse through the same
installed package. Either can be configured with an MCP client; run only the
one or ones the owner intends to offer.

## Install from the command line (optional)

The UI path above is preferred. If you want to manage the plugin through the
shell, add it through Omarchy's normal reviewable Git flow:

    omarchy plugin add https://github.com/univeracity/limitless-omarchy.git
    omarchy plugin enable univeracity.limitless-library

The panel can then be summoned with:

    omarchy-shell shell summon univeracity.limitless-library '{}'

To prefill a catalog path in the panel, supply it in the summon payload:

    omarchy-shell shell summon univeracity.limitless-library \
      '{"catalogPath":"/absolute/path/to/catalog"}'

Read the repository before enabling it. Omarchy shell plugins are unsandboxed
code in a long-lived desktop process. A valid manifest, matching digest, or
local adoption result is not a claim that arbitrary code is safe.

The Quattro contract supported by this repository is documented in
[Compatibility](docs/COMPATIBILITY.md).

For a real-session validation path, use the non-mutating
[runtime smoke test](docs/RUNTIME-SMOKE.md).

## Repository boundary

| Repository | Responsibility |
| --- | --- |
| Limitless Library | Generic local reuse core, capsule contracts, MCP and CLI surfaces, receipts, and conformance |
| This repository | Omarchy profile, Quattro panel, native validation integration, opt-in managed-service client, explicit generic-provider handoff, examples, and tests |
| Private Limitless service | Identity, policy, scopes, private catalog coordination, revocation, and managed verification |

## Status

Initial local-first implementation with one-action, release-pinned official
service activation and an advanced alternate-profile connector. No live
official identity is invented by this source tree, and the panel intentionally
exposes no capture or sharing control.

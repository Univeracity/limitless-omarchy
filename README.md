# Limitless Library for Omarchy

Local-first verified reuse for Omarchy customizations.

Before an agent creates a new customization, this adapter lets it ask whether
one owner-authorized prior result is eligible for the current Omarchy receiver.
It returns one exact component, one source-free method, or a safe abstention.

This repository contains a native Quattro panel and its companion CLI. It is
not an Omarchy plugin directory, package manager, or hosted service client.
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

The adapter works without a Limitless account or network connection. Its
default companion CLI:

- derives only a minimal receiver profile;
- does not inspect the user's plugin list, arbitrary desktop configuration,
  prompts, screenshots, command history, or agent workspace;
- does not silently install or enable a plugin; and
- leaves decisions and evidence local.

The managed Limitless service is deliberately outside this repository. It may
later coordinate private catalogs, identity, scopes, revocation, and
owner-authorized sharing. Connecting must never publish local work; capture
and sharing remain separate actions.

## Prerequisites

- An Omarchy release with the Quattro plugin contract.
- Python 3.11 or later.
- A local installation of Limitless Library.

Install the adapter. Its pinned public Limitless Library dependency is fetched
automatically:

    python3 -m pip install .

For offline development against a local Limitless Library checkout, install
that checkout first and then install this project with no dependency resolution.

    python3 -m pip install /path/to/limitlesslibrary
    python3 -m pip install --no-deps -e .

## Use the companion CLI

Inspect the minimal local receiver profile:

    limitless-omarchy status

Query a local Library catalog before a customization:

    limitless-omarchy query --catalog ./examples/catalog

Validate this plugin using Omarchy's own validator:

    limitless-omarchy validate-plugin .

The query returns a structured local-only result. An unavailable catalog,
missing core library, ambiguous candidate, or compatibility mismatch produces
an abstention rather than a best-effort selection.

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

## Install the Quattro panel

Once the companion CLI is installed, add the repository through Omarchy's
normal reviewable Git flow:

    omarchy plugin add https://github.com/univeracity/limitless-omarchy.git
    omarchy plugin enable univeracity.limitless-library

The panel is then summoned with:

    omarchy-shell shell summon univeracity.limitless-library '{}'

To query from the panel, supply a local catalog path in the summon payload:

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
| This repository | Omarchy profile, Quattro panel, native validation integration, explicit generic-provider handoff, examples, and tests |
| Private Limitless service | Identity, policy, scopes, private catalog coordination, revocation, and managed verification |

## Status

Initial local-first implementation. The panel has no hosted-service connection
and intentionally exposes no sharing control.

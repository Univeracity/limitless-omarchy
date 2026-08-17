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

The Quattro panel is a standalone third-party panel. It calls the companion
CLI only on the local machine. A caller can supply a catalog path in the
summon payload; otherwise the panel shows its local-only posture.

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

## Service boundary

The private Limitless service may later coordinate owner-authorized private
capsules across devices, organizations, and scoped exchange circles. It owns
identity, scopes, grants, revocation, and managed coordination. This plugin
must work without those facilities and must not make service connection imply
capture or publication.

# Security policy

## Scope

This repository contains an Omarchy shell plugin and a local Python companion
CLI. Omarchy plugins execute as unsandboxed code within a long-lived desktop
shell, so review this repository before enabling it.

The adapter intentionally does not claim that a validated component or a
successful local adoption is safe from arbitrary-code behavior. It establishes
only its documented structural, compatibility, delivery, and local-adoption
facts.

## Reporting

Do not open public issues for a suspected vulnerability. Report the affected
version, a concise reproduction, impact, and any suggested mitigation to the
maintainers through the private contact route listed by the Limitless Library
project.

## Data boundary

The local adapter does not transmit prompts, arbitrary configuration,
screenshots, desktop telemetry, command history, raw verifier output, or
agent workspace data.

Managed use is a distinct opt-in boundary. The owner supplies a profile that
pins endpoint, service identity, trust root, policy digest, data-use mode, and
scopes. Inspection sends no task. Query sends only the explicit objective and
minimal Omarchy receiver context. An optional bearer token travels over stdin,
is cleared with the objective after dispatch, and neither is stored in argv,
environment, profile, or disk by this plugin. Connecting does not publish a
capsule, upload a local catalog, install a result, or enable sharing.

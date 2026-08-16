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

The local adapter must not transmit prompts, arbitrary configuration,
screenshots, desktop telemetry, command history, raw verifier output, or
agent workspace data. A future managed-service connection must remain opt-in
and must not imply publication of local work.

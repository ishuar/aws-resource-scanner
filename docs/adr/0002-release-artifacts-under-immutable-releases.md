# ADR-0002: PyPI is the only artifact channel; releases stay immutable

- **Status:** accepted (2026-08-22)
- **Deciders:** ishuar

## Context

The v0.1.0 release pipeline failed at "Attach distributions to GitHub
release" with `HTTP 422: Cannot upload assets to an immutable release`.
The repository has GitHub's immutable releases enabled, which seals a
release the moment it is published — and release-please publishes
directly (`"draft": false`). So `gh release upload` could never work.
The failure skipped the PyPI job, leaving v0.1.0 tagged and released
with zero artifacts anywhere.

Two further problems surfaced while reading the workflow:

1. The build job attested provenance for artifacts it then discarded;
   the publish job ran `poetry build` again, so PyPI received
   differently-hashed files than the ones that were attested.
2. The PyPI job only runs on the push that creates a release, so any
   failure upstream left a released tag with no way to publish it.

## Decision

1. **PyPI is the only distribution channel.** The GitHub release keeps
   its notes, source archives, and provenance attestations; built
   sdists/wheels are not attached to it.
2. **Immutable releases stay enabled.** Disabling a supply-chain
   protection to make an upload succeed is the workaround CLAUDE.md
   rule 1 forbids. Rejected alternative: switch release-please to
   `draft: true`, upload assets, then publish — it works, but it buys
   duplicate artifacts on the release page at the cost of an extra
   config knob and making release visibility depend on the build.
3. **Build once, publish that build.** The build job uploads
   `dist/` as a workflow artifact; the publish job downloads it. The
   attestation now describes exactly what users install.
4. **`workflow_dispatch` accepts a `publish_tag` input** so an already
   released tag can be published to PyPI without a new release.

## Consequences

- Users install from PyPI (`pip install aws-resource-inventory`); the
  release page is notes plus source, not a download mirror.
- Recovering a half-finished release is a one-click manual dispatch, so
  a pipeline failure never strands a tag again.
- `publish_tag` is user input: it reaches shell only via `env`, never
  interpolated into a `run:` script, so it cannot inject commands.
- The build job dropped `contents: write` — nothing in it writes to the
  repository any more.

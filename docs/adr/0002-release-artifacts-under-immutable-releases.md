# ADR-0002: Publish releases as drafts, then seal them

- **Status:** accepted (2026-08-22)
- **Deciders:** ishuar

## Context

The v0.1.0 release pipeline failed at "Attach distributions to GitHub
release" with `HTTP 422: Cannot upload assets to an immutable release`.
This repository has GitHub's immutable releases enabled, and
release-please published the release directly (`"draft": false`), so the
release was sealed before the build job could attach anything. The failure
skipped the PyPI job, leaving v0.1.0 tagged and released with no artifacts
anywhere.

GitHub documents the flow for exactly this configuration: create the
release as a draft, attach assets, then publish it — immutability is
enforced only once a release is published.

Reading the workflow surfaced two more problems on the same path:

1. The build job attested provenance for artifacts it then discarded; the
   publish job ran `poetry build` again, so PyPI would have received
   differently-hashed files than the ones attested.
2. The PyPI job only runs on the push that creates a release, so any
   failure upstream left a released tag with no way to publish it.

## Decision

1. **Release as a draft, then publish it.** release-please sets
   `"draft": true`; the build job attaches the distributions and then
   publishes the draft. This is GitHub's documented pattern and the only
   way to have both attached assets and immutability.
2. **Immutability stays enabled.** Disabling a supply-chain protection to
   make an upload succeed is the workaround CLAUDE.md rule 1 forbids.
3. **Build once, publish that build.** The build job uploads `dist/` as a
   workflow artifact; the publish job downloads it instead of rebuilding,
   so the attestation describes exactly what users install.
4. **The recovery path never touches the GitHub release.**
   `workflow_dispatch` with a `publish_tag` input builds that tag and
   publishes it to PyPI only. An already-published release is immutable,
   so attaching to it is impossible by design — that is the 422 above.
5. **Build the released commit, not the tag.** Whether a draft release
   creates its git tag up front is undocumented, so the release path
   checks out `github.sha` (the commit that merged the release PR) and
   only the recovery path checks out a tag.

Rejected: keep publishing immediately and attach nothing, with PyPI as the
sole channel. It is simpler, but it only *recovers* from the failure above
instead of preventing it, and it declines the vendor-supported pattern for
no measurable gain.

## Consequences

- A published release always carries its artifacts; the state that
  stranded v0.1.0 cannot recur.
- v0.1.0 is already sealed, so it is recoverable only through decision 4 —
  build and publish to PyPI, leaving the release as it is.
- A failed build leaves the release as a draft, visible only to
  maintainers. Fix and re-run beats a published release pointing at
  nothing.
- The build job needs `contents: write` again to attach and publish.
- `publish_tag` is user input: it reaches shell only via `env`, never
  interpolated into a `run:` script, so it cannot inject commands.
- To watch on the next release: release-please must still report
  `release_created` for a draft release. If it does not, nothing publishes
  and the manual dispatch is the fallback.

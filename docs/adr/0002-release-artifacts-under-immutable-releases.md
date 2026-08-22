# ADR-0002: PyPI is the only artifact channel

- **Status:** accepted (2026-08-22)
- **Deciders:** ishuar

## Context

The v0.1.0 release pipeline failed at "Attach distributions to GitHub
release" with `HTTP 422: Cannot upload assets to an immutable release`.
This repository has GitHub's immutable releases enabled — a release is
sealed the moment it is published, and release-please publishes directly
— so that upload could never have worked. The failure skipped the PyPI
job, leaving v0.1.0 released with no artifacts anywhere.

Two further defects sat on the same path:

1. The build job attested provenance for artifacts it then discarded; the
   publish job ran `poetry build` again, so PyPI would have received
   different bytes than were attested.
2. The PyPI job only runs on the push that creates a release, so any
   failure upstream stranded the tag with no way to publish it.

## Decision

1. **PyPI is the only artifact channel.** No built distributions are
   attached to GitHub releases. The release keeps its notes, source
   archives, and provenance attestations.
2. **Immutable releases stay enabled.** Disabling a supply-chain
   protection to make an upload succeed is the workaround rule 1 forbids.
3. **Build once, publish that build.** The build job uploads `dist/` as a
   workflow artifact; the publish job downloads it instead of rebuilding,
   so the attestation describes exactly what users install.
4. **Prevent, don't just recover.** `ci.yml` runs `poetry build` and
   `twine check --strict` on every pull request, including
   release-please's release PR. Packaging breakage surfaces before a
   release exists.
5. **`workflow_dispatch` accepts a `publish_tag` input** to publish an
   already-released tag to PyPI without touching the release — the
   recovery path for a release that is already sealed.

### Rejected: draft the release, attach assets, then publish

GitHub documents this flow, and it is what an earlier revision of this
ADR chose. Three findings reversed that:

1. **GitHub's guidance answers a different question.** It says that *if*
   you attach assets under immutable releases, do it while the release is
   a draft. It is not a recommendation to attach build artifacts. Attach
   nothing and immutability stops being an obstacle at all.
2. **The norm for comparable projects is to attach nothing.** Of 21
   sampled Python projects, 11 attach nothing (httpx, pydantic, rich,
   typer, fastapi, httpie, sphinx, tox, …). Of the 10 that attach, half
   attach a native binary or `.pyz` — something PyPI cannot serve (ruff,
   uv, black, pipx, pre-commit). A pure-Python CLI attaching a wheel is
   just a PyPI mirror.
3. **`draft: true` alone corrupts the next release.** GitHub does not
   materialize the git tag for an unpublished draft, and release-please's
   release discovery filters out releases whose tag commit is null — so
   the following run cannot see its own last release, re-proposes the
   same version, and regenerates a whole-history changelog
   (release-please-action issues #1111, #962, #1169). Correct use needs
   `force-tag-creation: true` as well, added upstream in release-please
   17.2.0 for exactly this. So the flow costs two config flags, two
   conditional steps, `contents: write`, and two code paths through the
   build job — for artifacts we decided we do not want.

## Consequences

- Users install from PyPI (`pip install aws-resource-inventory`); the
  release page is notes plus source, not a download mirror.
- The build job needs only `contents: read`, and has one code path.
- A failed release build can still leave a published release ahead of
  PyPI. The pre-merge packaging check makes that unlikely and
  `publish_tag` makes it recoverable, which is the trade accepted here.
- `publish_tag` is user input: it reaches shell only via `env`, never
  interpolated into a `run:` script, so it cannot inject commands.
- Revisit this if the CLI ever ships a standalone binary or zipapp. Then
  the release page would carry something PyPI cannot, the draft flow
  earns its complexity, and `force-tag-creation: true` is mandatory with
  it.

## Never do this

**Do not delete a published release or its tag in order to retry.** A
tag name used by an immutable release is burned permanently: recreating
it returns `422 tag_name was used by an immutable release`. That survives
deleting the release, disabling the immutable-releases setting, and even
deleting and recreating the repository. So a release that shipped without
artifacts is fixed by publishing to PyPI beside it (decision 5), never by
recreating the release — a mistake that would cost the version number
forever.

Editing is narrower than it looks: after publish, only the **title and
release notes** stay editable. Assets and the tag are frozen.

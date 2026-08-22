# ADR-0003: Pin every GitHub Action to a commit SHA

- **Status:** accepted (2026-08-22)
- **Deciders:** ishuar

## Context

`release-please.yml` pinned every action to a full commit SHA with the
version in a trailing comment. `ci.yml` used floating major tags
(`actions/checkout@v7`, `codecov/codecov-action@v7`). Both conventions
lived in the same repository, so neither was a rule.

A floating tag is mutable: the owner can repoint `v7` at any commit, and
a compromised action then runs with the workflow's permissions and
secrets. It also breaks CLAUDE.md rule 2 — behaviour must never change
as a side effect of a version bump — because a run's actual code can
change with no diff in this repository.

## Decision

1. Every `uses:` reference is a full 40-character commit SHA, with the
   human-readable version as a trailing comment
   (`uses: actions/checkout@3d3c42e… # v7.0.1`).
2. Bumping an action means resolving the new tag to its SHA and updating
   both the pin and the comment, in a PR whose only concern is that bump
   (rule 5).
3. Verify a pin before committing it: resolve the tag through the GitHub
   API rather than copying a SHA from documentation or memory. When
   converting a floating tag, confirm the pin resolves to the same commit
   the tag resolves to today, so the change is behaviour-preserving.

## Consequences

- Dependabot/Renovate can still propose bumps; they update the pin and
  the comment together.
- Reviewers can diff exactly what code a workflow will run.
- A major bump is a deliberate act with release notes read first — how
  ADR-0002's artifact-action bump (upload v4→v7, download v4→v8) was
  handled.

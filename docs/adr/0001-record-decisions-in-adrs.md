# ADR-0001: Record engineering decisions in ADRs

- **Status:** accepted (2026-08-22)
- **Deciders:** ishuar

## Context

Engineering decisions (architecture, domain modelling, tooling, adopted
best practices) lived in PR descriptions, review threads, and session
memory — findable only by whoever was there. Only product decisions had
a durable home (`PRODUCT.md`'s decision log). Docs and AI sessions both
need one authoritative place to check *why* the code is shaped the way
it is.

## Decision

1. Every engineering decision gets one file:
   `docs/adr/NNNN-short-slug.md`, numbered sequentially, written when
   the decision is made.
2. Each ADR has exactly four parts: Status, Context, Decision,
   Consequences — in the i-have-adhd documentation style.
3. Superseding a decision means a new ADR that names the old one; the
   old ADR's status becomes `superseded by ADR-NNNN`. ADRs are never
   deleted.
4. Product decisions (*what* to build) stay in `PRODUCT.md`'s decision
   log; ADRs cover engineering decisions (*how* to build it).

## Consequences

- New decisions cost one small file in the PR that implements them
  (CLAUDE.md rule 15: docs ship in the same PR as the change).
- Reviewers can reject a PR for missing an ADR the way they would for
  a missing test.
- This file is the template: copy it, renumber, replace the content.
